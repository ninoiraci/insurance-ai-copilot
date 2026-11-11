"""Structured-output validation: the contract between the LLM and the system."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import InsuranceType, Intent, RecommendedAction, Team, Urgency
from app.schemas.ai_output import ExtractedEntities, GeneratedResponse, MessageAnalysis
from app.services.ai.structured import extract_json_object

VALID_PAYLOAD = {
    "intent": "CLAIM",
    "insurance_type": "MOTOR",
    "urgency": "MEDIUM",
    "confidence": 0.94,
    "summary": "Customer reports a minor collision with no injuries.",
    "extracted_entities": {"vehicle_plate": "1234 abc", "injuries": "no"},
    "missing_information": ["accident location"],
    "recommended_action": "REQUEST_DOCUMENTS",
    "assigned_team": "CLAIMS_TEAM",
    "human_review_required": True,
}


def test_valid_payload_parses_into_enums():
    analysis = MessageAnalysis.model_validate(VALID_PAYLOAD)

    assert analysis.intent is Intent.CLAIM
    assert analysis.insurance_type is InsuranceType.MOTOR
    assert analysis.urgency is Urgency.MEDIUM
    assert analysis.recommended_action is RecommendedAction.REQUEST_DOCUMENTS
    assert analysis.assigned_team is Team.CLAIMS_TEAM


def test_entity_normalisation():
    """Plates lose spacing, Spanish/English booleans are coerced."""
    analysis = MessageAnalysis.model_validate(VALID_PAYLOAD)
    entities = analysis.extracted_entities

    assert entities.vehicle_plate == "1234ABC"
    assert entities.injuries is False
    assert "third_party_involved" not in entities.as_dict()


@pytest.mark.parametrize("raw,expected", [("sí", True), ("no", False), ("maybe", None)])
def test_boolean_coercion(raw, expected):
    assert ExtractedEntities(injuries=raw).injuries is expected


def test_unknown_intent_falls_back_instead_of_raising():
    """An invented label must never reach the database, but it is recoverable."""
    payload = {**VALID_PAYLOAD, "intent": "REFUND_REQUEST"}
    assert MessageAnalysis.model_validate(payload).intent is Intent.UNKNOWN


def test_invalid_urgency_is_rejected():
    """Urgency has operational consequences; silently defaulting it is unsafe."""
    payload = {**VALID_PAYLOAD, "urgency": "SUPER_URGENT"}
    with pytest.raises(ValidationError):
        MessageAnalysis.model_validate(payload)


def test_confidence_out_of_range_is_rescaled():
    assert MessageAnalysis.model_validate({**VALID_PAYLOAD, "confidence": 94}).confidence == 0.94


def test_confidence_above_one_but_not_percentage_is_rejected():
    with pytest.raises(ValidationError):
        MessageAnalysis.model_validate({**VALID_PAYLOAD, "confidence": 1500})


def test_incoherent_unknown_intent_confidence_is_capped():
    """High confidence in "I don't know" is a contradiction, not a signal."""
    payload = {**VALID_PAYLOAD, "intent": "UNKNOWN", "confidence": 0.97}
    assert MessageAnalysis.model_validate(payload).confidence == 0.4


def test_missing_required_field_raises():
    payload = {key: value for key, value in VALID_PAYLOAD.items() if key != "summary"}
    with pytest.raises(ValidationError):
        MessageAnalysis.model_validate(payload)


def test_missing_information_accepts_a_bare_string():
    payload = {**VALID_PAYLOAD, "missing_information": "accident photographs"}
    assert MessageAnalysis.model_validate(payload).missing_information == [
        "accident photographs"
    ]


def test_allowed_values_fragment_is_generated_from_the_enums():
    fragment = MessageAnalysis.json_schema_prompt_fragment()
    for intent in Intent.values():
        assert intent in fragment


def test_generated_response_coerces_single_source():
    response = GeneratedResponse(response_text="Hola", used_sources="Doc, section 1")
    assert response.used_sources == ["Doc, section 1"]


class TestJsonExtraction:
    def test_plain_object(self):
        assert extract_json_object('{"a": 1}') == '{"a": 1}'

    def test_markdown_fenced(self):
        assert extract_json_object('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_surrounded_by_prose(self):
        raw = 'Sure! Here is the analysis:\n{"a": 1}\nLet me know if you need more.'
        assert extract_json_object(raw) == '{"a": 1}'

    def test_braces_inside_strings_do_not_confuse_the_parser(self):
        raw = '{"summary": "he said {this} and }that{"}'
        assert extract_json_object(raw) == raw

    def test_empty_response_raises(self):
        with pytest.raises(ValueError):
            extract_json_object("   ")

    def test_no_object_raises(self):
        with pytest.raises(ValueError):
            extract_json_object("I cannot help with that request.")

    def test_unterminated_object_raises(self):
        with pytest.raises(ValueError):
            extract_json_object('{"a": 1')
