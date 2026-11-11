"""Request validation schemas for the REST API.

Using Pydantic for inbound payloads too keeps validation in one place and
gives consistent 422 error bodies instead of ad-hoc `if not data.get(...)`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.enums import ReviewerAction


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: int | None = None
    # Re-running analysis is allowed but must be explicit: it costs money and
    # creates a second audit record.
    force: bool = False


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ReviewerAction
    final_response: str | None = Field(default=None, max_length=6000)
    reviewer_notes: str | None = Field(default=None, max_length=2000)
    reviewer_name: str = Field(default="demo.operator", max_length=120)

    @field_validator("action", mode="before")
    @classmethod
    def _coerce_action(cls, value: object) -> object:
        coerced = ReviewerAction.coerce(value)
        if coerced is None:
            raise ValueError(
                f"action must be one of {ReviewerAction.values()}"
            )
        return coerced

    @field_validator("final_response")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    def resolved_response(self, original: str) -> str | None:
        if self.action == ReviewerAction.REJECT:
            return None
        if self.action == ReviewerAction.EDIT_AND_APPROVE:
            if not self.final_response:
                raise ValueError("final_response is required for EDIT_AND_APPROVE")
            return self.final_response
        return original


class KnowledgeSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force: bool = False


class EvaluationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(default="manual run", max_length=120)
    limit: int | None = Field(default=None, ge=1, le=500)
