"""AI analysis and human review models.

Every AI decision is persisted with the exact model, prompt version and
latency that produced it. That is what makes the system auditable: months
later you can still answer "which prompt produced this recommendation?".
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import JSONColumn, Model, TimestampMixin, enum_column, utcnow
from .enums import (
    InsuranceType,
    Intent,
    RecommendedAction,
    ReviewerAction,
    Team,
    Urgency,
)


class AIAnalysis(Model, TimestampMixin):
    __tablename__ = "ai_analyses"

    conversation_id: Mapped[int] = mapped_column(
        sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )

    intent: Mapped[Intent] = mapped_column(enum_column(Intent), nullable=False, index=True)
    insurance_type: Mapped[InsuranceType] = mapped_column(
        enum_column(InsuranceType), nullable=False, index=True
    )
    urgency: Mapped[Urgency] = mapped_column(enum_column(Urgency), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(sa.Float, nullable=False)
    summary: Mapped[str] = mapped_column(sa.Text, nullable=False)

    extracted_entities: Mapped[dict] = mapped_column(JSONColumn, default=dict, nullable=False)
    missing_information: Mapped[list] = mapped_column(JSONColumn, default=list, nullable=False)

    recommended_action: Mapped[RecommendedAction] = mapped_column(
        enum_column(RecommendedAction), nullable=False, index=True
    )
    assigned_team: Mapped[Team] = mapped_column(enum_column(Team), nullable=False)
    action_reason: Mapped[str | None] = mapped_column(sa.Text)
    follow_up_hours: Mapped[int | None] = mapped_column(sa.Integer)

    suggested_response: Mapped[str] = mapped_column(sa.Text, nullable=False)
    human_review_required: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, nullable=False, index=True
    )
    review_reasons: Mapped[list] = mapped_column(JSONColumn, default=list, nullable=False)

    # RAG provenance: exactly which chunks the response was allowed to use.
    retrieved_sources: Mapped[list] = mapped_column(JSONColumn, default=list, nullable=False)
    grounded: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)

    # Reliability + observability metadata.
    model_name: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    processing_latency_ms: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    demo_mode: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    validation_attempts: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    rule_overrides: Mapped[list] = mapped_column(JSONColumn, default=list, nullable=False)
    safety_flags: Mapped[list] = mapped_column(JSONColumn, default=list, nullable=False)
    token_usage: Mapped[dict | None] = mapped_column(JSONColumn)

    conversation: Mapped["Conversation"] = relationship(back_populates="analyses")  # noqa: F821
    reviews: Mapped[list["HumanReview"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", order_by="HumanReview.timestamp"
    )

    @property
    def latest_review(self) -> "HumanReview | None":
        return self.reviews[-1] if self.reviews else None

    def to_summary_dict(self) -> dict:
        """Compact shape used by list views (inbox, dashboard)."""
        review = self.latest_review
        return {
            "id": self.id,
            "intent": self.intent.value,
            "insurance_type": self.insurance_type.value,
            "urgency": self.urgency.value,
            "confidence": round(self.confidence, 3),
            "recommended_action": self.recommended_action.value,
            "assigned_team": self.assigned_team.value,
            "human_review_required": self.human_review_required,
            "demo_mode": self.demo_mode,
            "reviewed": review is not None,
            "reviewer_action": review.reviewer_action.value if review else None,
            "created_at": self.created_at.isoformat(),
        }

    def to_dict(self) -> dict:
        return {
            **self.to_summary_dict(),
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "summary": self.summary,
            "extracted_entities": self.extracted_entities or {},
            "missing_information": self.missing_information or [],
            "action_reason": self.action_reason,
            "follow_up_hours": self.follow_up_hours,
            "suggested_response": self.suggested_response,
            "review_reasons": self.review_reasons or [],
            "retrieved_sources": self.retrieved_sources or [],
            "grounded": self.grounded,
            "rule_overrides": self.rule_overrides or [],
            "safety_flags": self.safety_flags or [],
            "reviews": [review.to_dict() for review in self.reviews],
            "metadata": {
                "model_name": self.model_name,
                "prompt_version": self.prompt_version,
                "processing_latency_ms": self.processing_latency_ms,
                "demo_mode": self.demo_mode,
                "validation_attempts": self.validation_attempts,
                "retrieved_chunk_count": len(self.retrieved_sources or []),
                "token_usage": self.token_usage,
                "created_at": self.created_at.isoformat(),
            },
        }


class HumanReview(Model):
    __tablename__ = "human_reviews"

    ai_analysis_id: Mapped[int] = mapped_column(
        sa.ForeignKey("ai_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_action: Mapped[ReviewerAction] = mapped_column(
        enum_column(ReviewerAction), nullable=False
    )
    reviewer_name: Mapped[str] = mapped_column(sa.String(120), default="demo.operator")
    original_response: Mapped[str] = mapped_column(sa.Text, nullable=False)
    final_response: Mapped[str | None] = mapped_column(sa.Text)
    reviewer_notes: Mapped[str | None] = mapped_column(sa.Text)
    # POC: nothing is really sent. We record the intent to send instead.
    simulated_send: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(sa.DateTime, default=utcnow, nullable=False)

    analysis: Mapped[AIAnalysis] = relationship(back_populates="reviews")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ai_analysis_id": self.ai_analysis_id,
            "reviewer_action": self.reviewer_action.value,
            "reviewer_name": self.reviewer_name,
            "original_response": self.original_response,
            "final_response": self.final_response,
            "reviewer_notes": self.reviewer_notes,
            "simulated_send": self.simulated_send,
            "timestamp": self.timestamp.isoformat(),
        }
