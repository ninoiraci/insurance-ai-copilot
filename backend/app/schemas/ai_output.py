"""Pydantic contracts for every LLM output.

The analytical stage never returns free text. The model must produce JSON that
validates against `MessageAnalysis`; anything else is a hard failure that
triggers a retry and, if it still fails, a safe fallback. This is the single
most important reliability control in the project: an invalid label can never
reach the database, the routing engine or the UI.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..models.enums import (
    InsuranceType,
    Intent,
    RecommendedAction,
    Team,
    Urgency,
)

class ExtractedEntities(BaseModel):
    """Loosely typed entity bag: known keys are normalised, extras preserved."""

    model_config = ConfigDict(extra="allow")

    vehicle_plate: str | None = None
    policy_number: str | None = None
    incident_date: str | None = None
    incident_location: str | None = None
    injuries: bool | None = None
    third_party_involved: bool | None = None
    damage_description: str | None = None
    amount: float | None = None
    expiration_date: str | None = None

    @field_validator("vehicle_plate", "policy_number", mode="before")
    @classmethod
    def _normalise_identifier(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = value.replace(" ", "").replace("-", "").upper().strip()
            return cleaned or None
        return value

    @field_validator("injuries", "third_party_involved", mode="before")
    @classmethod
    def _coerce_bool(cls, value: Any) -> Any:
        """LLMs return "no", "false", "ninguno"... accept the obvious spellings."""
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "yes", "si", "sí", "y", "1"}:
                return True
            if lowered in {"false", "no", "n", "0", "none", "ninguno", "ninguna"}:
                return False
            return None
        return value

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = value.replace("€", "").replace(",", ".").strip()
            try:
                return float(cleaned)
            except ValueError:
                return None
        return value

    def as_dict(self) -> dict[str, Any]:
        """Drop nulls so the UI and evaluator only see extracted facts."""
        return {
            key: value
            for key, value in self.model_dump(exclude_none=True).items()
            if value != "" and value != []
        }


class MessageAnalysis(BaseModel):
    """The classification + extraction contract (prompt `classification_v1`)."""

    model_config = ConfigDict(extra="ignore", use_enum_values=False)

    intent: Intent
    insurance_type: InsuranceType
    urgency: Urgency
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1, max_length=800)
    extracted_entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    missing_information: list[str] = Field(default_factory=list, max_length=10)
    recommended_action: RecommendedAction = RecommendedAction.ESCALATE_TO_HUMAN
    assigned_team: Team = Team.UNASSIGNED
    human_review_required: bool = True
    reasoning: str | None = Field(default=None, max_length=1000)

    @field_validator("intent", mode="before")
    @classmethod
    def _coerce_intent(cls, value: Any) -> Any:
        return Intent.coerce(value, Intent.UNKNOWN) or Intent.UNKNOWN

    @field_validator("insurance_type", mode="before")
    @classmethod
    def _coerce_insurance(cls, value: Any) -> Any:
        return InsuranceType.coerce(value, InsuranceType.UNKNOWN) or InsuranceType.UNKNOWN

    @field_validator("urgency", mode="before")
    @classmethod
    def _coerce_urgency(cls, value: Any) -> Any:
        coerced = Urgency.coerce(value)
        if coerced is None:
            # Refusing to guess is safer than defaulting low; MEDIUM keeps the
            # case visible without falsely escalating.
            raise ValueError(f"unknown urgency value: {value!r}")
        return coerced

    @field_validator("recommended_action", mode="before")
    @classmethod
    def _coerce_action(cls, value: Any) -> Any:
        return RecommendedAction.coerce(value, RecommendedAction.ESCALATE_TO_HUMAN)

    @field_validator("assigned_team", mode="before")
    @classmethod
    def _coerce_team(cls, value: Any) -> Any:
        return Team.coerce(value, Team.UNASSIGNED)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: Any) -> Any:
        if isinstance(value, str):
            try:
                value = float(value.strip().rstrip("%"))
            except ValueError as exc:
                raise ValueError(f"confidence not numeric: {value!r}") from exc
        if isinstance(value, (int, float)) and value > 1.0:
            # Models sometimes emit 94 instead of 0.94.
            return round(float(value) / 100.0, 4)
        return value

    @field_validator("missing_information", mode="before")
    @classmethod
    def _coerce_missing(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()][:10]
        return []

    @model_validator(mode="after")
    def _consistency(self) -> "MessageAnalysis":
        """Cheap internal consistency check before business rules take over."""
        if self.intent == Intent.UNKNOWN and self.confidence > 0.6:
            # An UNKNOWN intent asserted with high confidence is incoherent.
            self.confidence = 0.4
        return self

    def to_storage_dict(self) -> dict[str, Any]:
        """Model-owned fields only.

        `urgency` is deliberately absent: the deterministic rule engine owns
        the final value, and the caller supplies it. Leaving it here invited
        the pipeline to overwrite this object in place, which silently
        destroyed the model's own answer.
        """
        return {
            "intent": self.intent,
            "insurance_type": self.insurance_type,
            "confidence": self.confidence,
            "summary": self.summary,
            "extracted_entities": self.extracted_entities.as_dict(),
            "missing_information": self.missing_information,
        }

    @staticmethod
    def json_schema_prompt_fragment() -> str:
        """Enum lists injected into the prompt, generated from the same source."""
        return json.dumps(
            {
                "intent": Intent.values(),
                "insurance_type": InsuranceType.values(),
                "urgency": Urgency.values(),
                "recommended_action": RecommendedAction.values(),
                "assigned_team": Team.values(),
            },
            indent=2,
        )


class GeneratedResponse(BaseModel):
    """Contract for the customer-facing draft (prompt `response_v1`)."""

    model_config = ConfigDict(extra="ignore")

    response_text: str = Field(min_length=1, max_length=4000)
    used_sources: list[str] = Field(default_factory=list)
    grounded: bool = True
    # Set by the model when the knowledge base does not support a safe answer.
    insufficient_information: bool = False

    @field_validator("used_sources", mode="before")
    @classmethod
    def _coerce_sources(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]


class AnalysisFailure(Exception):
    """Raised when the AI layer cannot produce a usable, validated result."""

    def __init__(self, message: str, *, attempts: int = 0, raw: str | None = None) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.raw = raw
