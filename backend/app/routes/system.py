"""Health, configuration and dashboard endpoints."""

from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, jsonify
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    AIAnalysis,
    Conversation,
    ConversationStatus,
    Customer,
    HumanReview,
    KnowledgeChunk,
    KnowledgeDocument,
    Policy,
    ReviewerAction,
    Task,
    TaskStatus,
    Urgency,
    utcnow,
)
from ..services.rag.vector_store import get_vector_store
from .helpers import get_ai_stack

bp = Blueprint("system", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    """Liveness + a real dependency check on the database."""
    database_ok = True
    try:
        db.session.execute(select(1))
    except Exception:  # pragma: no cover - only when the DB is genuinely down
        database_ok = False

    ai = get_ai_stack()
    status = "ok" if database_ok else "degraded"
    return (
        jsonify(
            {
                "status": status,
                "database": "ok" if database_ok else "unavailable",
                "vector_backend": get_vector_store().backend if database_ok else "unknown",
                "ai_demo_mode": ai.demo_mode,
                "model": ai.provider.model,
            }
        ),
        200 if database_ok else 503,
    )


@bp.get("/config")
def config():
    """What the frontend needs to render honest labels (e.g. Demo AI Mode)."""
    ai = get_ai_stack()
    return jsonify(
        {
            "ai": ai.describe(),
            "vector_backend": get_vector_store().backend,
            "brokerage_name": "Correduría Ejemplo",
            "data_notice": "All data in this system is synthetic. No real customers exist.",
        }
    )


def _distribution(counts: dict) -> list[dict]:
    """Enum->count map as a list of labels, busiest first."""
    return [
        {"label": key.value, "count": value}
        for key, value in sorted(counts.items(), key=lambda item: -item[1])
    ]


def _count(column, *conditions) -> int:
    """`SELECT count(...) WHERE ...` - the dashboard does this a dozen times."""
    statement = select(func.count(column))
    if conditions:
        statement = statement.where(*conditions)
    return db.session.scalar(statement) or 0


def _group_counts(column) -> dict:
    """`SELECT column, count(*) GROUP BY column` as a plain dict."""
    return dict(
        db.session.execute(select(column, func.count()).group_by(column)).all()
    )


@bp.get("/dashboard")
def dashboard():
    day_ago = utcnow() - timedelta(days=1)

    OPEN_STATUSES = [
        ConversationStatus.NEW,
        ConversationStatus.AI_PROCESSED,
        ConversationStatus.PENDING_REVIEW,
        ConversationStatus.ESCALATED,
    ]

    # Everything below is aggregated in SQL. Loading every analysis and review
    # into Python to average two columns is a full table scan per render.
    analysis_count, avg_confidence, avg_latency = db.session.execute(
        select(
            func.count(AIAnalysis.id),
            func.avg(AIAnalysis.confidence),
            func.avg(AIAnalysis.processing_latency_ms),
        )
    ).one()

    reviews_by_action = _group_counts(HumanReview.reviewer_action)
    approved = reviews_by_action.get(ReviewerAction.APPROVE, 0)
    edited = reviews_by_action.get(ReviewerAction.EDIT_AND_APPROVE, 0)
    rejected = reviews_by_action.get(ReviewerAction.REJECT, 0)
    reviewed = approved + edited + rejected

    analyses_by_intent = _group_counts(AIAnalysis.intent)
    analyses_by_urgency = _group_counts(AIAnalysis.urgency)
    conversations_by_channel = _group_counts(Conversation.channel)

    recent = (
        db.session.execute(
            select(Conversation)
            .options(
                selectinload(Conversation.customer),
                selectinload(Conversation.messages),
                selectinload(Conversation.analyses).selectinload(AIAnalysis.reviews),
            )
            .order_by(Conversation.updated_at.desc())
            .limit(8)
        )
        .scalars()
        .all()
    )

    return jsonify(
        {
            "metrics": {
                "open_conversations": _count(
                    Conversation.id, Conversation.status.in_(OPEN_STATUSES)
                ),
                "total_conversations": _count(Conversation.id),
                "ai_processed_last_24h": _count(
                    AIAnalysis.id, AIAnalysis.created_at >= day_ago
                ),
                "pending_human_review": _count(
                    Conversation.id,
                    Conversation.status == ConversationStatus.PENDING_REVIEW,
                ),
                "high_priority_cases": _count(
                    AIAnalysis.id,
                    AIAnalysis.urgency.in_([Urgency.HIGH, Urgency.CRITICAL]),
                ),
                "avg_confidence": round(float(avg_confidence), 3) if analysis_count else 0.0,
                "avg_latency_ms": int(avg_latency) if analysis_count else 0,
                "approval_rate": round((approved + edited) / reviewed, 3) if reviewed else None,
                "edit_rate": round(edited / reviewed, 3) if reviewed else None,
                "reviews_recorded": reviewed,
                "customers": _count(Customer.id),
                "policies": _count(Policy.id),
                "open_tasks": _count(Task.id, Task.status == TaskStatus.OPEN),
                "knowledge_documents": _count(KnowledgeDocument.id),
                "knowledge_chunks": _count(KnowledgeChunk.id),
            },
            "distributions": {
                "intent": _distribution(analyses_by_intent),
                # Every urgency level is listed, including the empty ones, so
                # the chart keeps a stable shape.
                "urgency": [
                    {"label": level.value, "count": analyses_by_urgency.get(level, 0)}
                    for level in Urgency
                ],
                "channel": _distribution(conversations_by_channel),
            },
            "human_review": {
                "required": _count(
                    AIAnalysis.id, AIAnalysis.human_review_required.is_(True)
                ),
                "reviewed": reviewed,
                "approved": approved,
                "edited": edited,
                "rejected": rejected,
            },
            "recent_conversations": [conversation.to_dict() for conversation in recent],
        }
    )
