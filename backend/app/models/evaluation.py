"""Evaluation dataset and persisted evaluation runs.

Runs are stored so that prompt changes can be compared over time - the
question "did prompt v2 make intent accuracy better or worse?" needs history.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import JSONColumn, Model, TimestampMixin, enum_column
from .enums import InsuranceType, Intent, RecommendedAction, Urgency


class EvaluationCase(Model, TimestampMixin):
    __tablename__ = "evaluation_cases"

    case_key: Mapped[str] = mapped_column(sa.String(40), unique=True, nullable=False)
    input_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    channel: Mapped[str] = mapped_column(sa.String(20), default="WHATSAPP", nullable=False)
    difficulty: Mapped[str] = mapped_column(sa.String(20), default="STANDARD", nullable=False)
    notes: Mapped[str | None] = mapped_column(sa.Text)

    expected_intent: Mapped[Intent] = mapped_column(enum_column(Intent), nullable=False)
    expected_urgency: Mapped[Urgency] = mapped_column(enum_column(Urgency), nullable=False)
    expected_insurance_type: Mapped[InsuranceType] = mapped_column(
        enum_column(InsuranceType), nullable=False
    )
    expected_action: Mapped[RecommendedAction] = mapped_column(
        enum_column(RecommendedAction), nullable=False
    )
    expected_entities: Mapped[dict] = mapped_column(JSONColumn, default=dict, nullable=False)
    expects_human_review: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_key": self.case_key,
            "input_text": self.input_text,
            "channel": self.channel,
            "difficulty": self.difficulty,
            "notes": self.notes,
            "expected_intent": self.expected_intent.value,
            "expected_urgency": self.expected_urgency.value,
            "expected_insurance_type": self.expected_insurance_type.value,
            "expected_action": self.expected_action.value,
            "expected_entities": self.expected_entities or {},
            "expects_human_review": self.expects_human_review,
        }


class EvaluationRun(Model, TimestampMixin):
    __tablename__ = "evaluation_runs"

    label: Mapped[str] = mapped_column(sa.String(120), default="manual run", nullable=False)
    model_name: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    demo_mode: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    case_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONColumn, default=dict, nullable=False)
    duration_ms: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)

    results: Mapped[list["EvaluationResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="EvaluationResult.id"
    )

    def to_dict(self, *, include_results: bool = False) -> dict:
        payload = {
            "id": self.id,
            "label": self.label,
            "model_name": self.model_name,
            "prompt_version": self.prompt_version,
            "demo_mode": self.demo_mode,
            "case_count": self.case_count,
            "metrics": self.metrics or {},
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat(),
        }
        if include_results:
            payload["results"] = [result.to_dict() for result in self.results]
        return payload


class EvaluationResult(Model):
    """Per-case outcome, kept so failures can be inspected individually."""

    __tablename__ = "evaluation_results"

    run_id: Mapped[int] = mapped_column(
        sa.ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_key: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    predicted: Mapped[dict] = mapped_column(JSONColumn, default=dict, nullable=False)
    expected: Mapped[dict] = mapped_column(JSONColumn, default=dict, nullable=False)
    correctness: Mapped[dict] = mapped_column(JSONColumn, default=dict, nullable=False)
    latency_ms: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    schema_valid: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    error: Mapped[str | None] = mapped_column(sa.Text)

    run: Mapped[EvaluationRun] = relationship(back_populates="results")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "case_key": self.case_key,
            "predicted": self.predicted or {},
            "expected": self.expected or {},
            "correctness": self.correctness or {},
            "latency_ms": self.latency_ms,
            "schema_valid": self.schema_valid,
            "error": self.error,
        }
