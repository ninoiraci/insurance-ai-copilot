"""Retry, fallback and provider-failure behaviour of the structured client.

The LLM is mocked here on purpose: these tests are about what happens when a
model misbehaves, which is exactly what a real model will not do on demand.
"""

from __future__ import annotations

import pytest

from app.schemas.ai_output import AnalysisFailure, MessageAnalysis
from app.services.ai.base import LLMError, LLMProvider, LLMResponse
from app.services.ai.structured import StructuredLLMClient

VALID_JSON = """
{"intent": "CLAIM", "insurance_type": "MOTOR", "urgency": "MEDIUM",
 "confidence": 0.9, "summary": "Collision reported.",
 "extracted_entities": {}, "missing_information": [],
 "recommended_action": "REQUEST_DOCUMENTS", "assigned_team": "CLAIMS_TEAM",
 "human_review_required": true}
"""


class ScriptedProvider(LLMProvider):
    """Returns a scripted sequence of replies (or raises scripted errors)."""

    name = "scripted"

    def __init__(self, replies: list[str | Exception]) -> None:
        super().__init__(model="scripted-1", temperature=0.0, max_tokens=100, timeout=5)
        self.replies = list(replies)
        self.calls: list[str] = []

    def complete(self, system: str, user: str) -> LLMResponse:
        self.calls.append(user)
        # Repeat the final reply so a test can exhaust retries on both the
        # classification call and the response-generation call.
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return LLMResponse(text=reply, model=self.model, latency_ms=5)


def generate(provider: ScriptedProvider, retries: int = 2):
    return StructuredLLMClient(provider, max_retries=retries).generate(
        schema=MessageAnalysis, system="sys", user="usr", label="test"
    )


def test_first_attempt_success_makes_one_call():
    provider = ScriptedProvider([VALID_JSON])
    analysis, _, attempts = generate(provider)

    assert attempts == 1
    assert len(provider.calls) == 1
    assert analysis.intent.value == "CLAIM"


def test_malformed_json_triggers_a_retry():
    provider = ScriptedProvider(["not json at all", VALID_JSON])
    analysis, _, attempts = generate(provider)

    assert attempts == 2
    assert analysis.intent.value == "CLAIM"


def test_retry_prompt_includes_the_validation_error():
    """A blind retry wastes a call; the model is told what it got wrong."""
    bad = '{"intent": "CLAIM", "urgency": "VERY_URGENT"}'
    provider = ScriptedProvider([bad, VALID_JSON])
    generate(provider)

    assert "rejected by the schema validator" in provider.calls[1]
    assert "urgency" in provider.calls[1]


def test_schema_violation_retries_then_succeeds():
    provider = ScriptedProvider(['{"intent": "CLAIM"}', VALID_JSON])
    _, _, attempts = generate(provider)
    assert attempts == 2


def test_exhausted_retries_raise_analysis_failure():
    provider = ScriptedProvider(["nope", "still nope", "nope again"])
    with pytest.raises(AnalysisFailure) as exc_info:
        generate(provider, retries=2)

    assert exc_info.value.attempts == 3
    assert len(provider.calls) == 3


def test_retryable_provider_error_is_retried():
    provider = ScriptedProvider([LLMError("rate limited", retryable=True), VALID_JSON])
    _, _, attempts = generate(provider)
    assert attempts == 2


def test_non_retryable_provider_error_fails_immediately():
    provider = ScriptedProvider([LLMError("bad api key", retryable=False), VALID_JSON])
    with pytest.raises(AnalysisFailure):
        generate(provider)

    assert len(provider.calls) == 1, "a 401 must not be retried"


def test_pipeline_falls_back_safely_when_the_model_never_validates(app, pipeline, monkeypatch):
    """A dead model degrades the product; it must not corrupt the database."""
    broken = ScriptedProvider(["garbage"] * 5)
    monkeypatch.setattr(pipeline.ai.client, "provider", broken)

    result = pipeline.run(raw_message="Tuve un accidente con el coche", context=None)

    assert result.fallback_used is True
    assert result.analysis.intent.value == "UNKNOWN"
    assert result.analysis.confidence == 0.0
    assert result.review.required is True
    assert result.action.recommended_action.value in {
        "ESCALATE_TO_HUMAN",
        "REQUEST_CLARIFICATION",
    }
