"""Unified inbox and conversation detail, including triggering AI analysis."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    AIAnalysis,
    Channel,
    Conversation,
    ConversationStatus,
    Customer,
    InsuranceType,
    Intent,
    Message,
    SenderType,
    Urgency,
)
from ..schemas.api import AnalyzeRequest
from ..services.workflows.context import build_customer_context
from ..utils.errors import ConflictError, NotFoundError, ValidationFailed
from .helpers import get_pipeline, int_arg, parse_body

logger = logging.getLogger(__name__)

bp = Blueprint("conversations", __name__, url_prefix="/api/conversations")


def _load(conversation_id: int) -> Conversation:
    conversation = db.session.get(Conversation, conversation_id)
    if conversation is None:
        raise NotFoundError(f"Conversation {conversation_id} does not exist.")
    return conversation


def _enum_filter(name: str, enum_cls):
    raw = request.args.get(name)
    if not raw:
        return None
    value = enum_cls.coerce(raw)
    if value is None:
        raise ValidationFailed(
            f"Invalid {name} '{raw}'. Allowed values: {', '.join(enum_cls.values())}."
        )
    return value


@bp.get("")
def list_conversations():
    """Inbox listing. Filtering by AI labels happens in Python, deliberately.

    Intent/urgency live on the latest analysis, not the conversation, so a SQL
    filter would need a correlated subquery for "latest per conversation". At
    POC data volumes that complexity is not worth it; the trade-off is noted in
    docs/ARCHITECTURE.md.
    """
    search = (request.args.get("search") or "").strip()
    limit = int_arg("limit", 100, maximum=500)

    channel = _enum_filter("channel", Channel)
    status = _enum_filter("status", ConversationStatus)
    intent = _enum_filter("intent", Intent)
    urgency = _enum_filter("urgency", Urgency)
    insurance_type = _enum_filter("insurance_type", InsuranceType)
    review_only = request.args.get("review_required") in {"1", "true", "yes"}

    # `to_dict()` reads customer, messages and the latest analysis for every
    # row. Without eager loading this listing issues ~3 queries per
    # conversation instead of a constant number.
    statement = (
        select(Conversation)
        .join(Customer, Conversation.customer_id == Customer.id)
        .options(
            selectinload(Conversation.customer),
            selectinload(Conversation.messages),
            selectinload(Conversation.analyses).selectinload(AIAnalysis.reviews),
        )
        .order_by(Conversation.updated_at.desc())
    )
    if channel:
        statement = statement.where(Conversation.channel == channel)
    if status:
        statement = statement.where(Conversation.status == status)
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(
                Customer.full_name.ilike(pattern),
                Conversation.subject.ilike(pattern),
                Conversation.reference.ilike(pattern),
            )
        )

    conversations = db.session.execute(statement).scalars().all()

    def keep(conversation: Conversation) -> bool:
        analysis = conversation.latest_analysis
        if intent and (analysis is None or analysis.intent != intent):
            return False
        if urgency and (analysis is None or analysis.urgency != urgency):
            return False
        if insurance_type and (analysis is None or analysis.insurance_type != insurance_type):
            return False
        if review_only and (analysis is None or not analysis.human_review_required):
            return False
        return True

    filtered = [conversation for conversation in conversations if keep(conversation)][:limit]
    return jsonify(
        {
            "items": [conversation.to_dict() for conversation in filtered],
            "count": len(filtered),
            "filters": {
                "channels": Channel.values(),
                "statuses": ConversationStatus.values(),
                "intents": Intent.values(),
                "urgencies": Urgency.values(),
                "insurance_types": InsuranceType.values(),
            },
        }
    )


@bp.get("/<int:conversation_id>")
def get_conversation(conversation_id: int):
    conversation = _load(conversation_id)
    payload = conversation.to_dict(include_messages=True)
    payload["customer"] = conversation.customer.to_dict(include_relations=True)
    payload["ai_context"] = build_customer_context(
        conversation.customer, exclude_conversation_id=conversation.id
    ).to_dict()
    payload["analyses"] = [analysis.to_dict() for analysis in conversation.analyses]
    payload["tasks"] = [task.to_dict() for task in conversation.tasks]
    return jsonify(payload)


@bp.post("/<int:conversation_id>/analyze")
def analyze_conversation(conversation_id: int):
    conversation = _load(conversation_id)
    body = parse_body(AnalyzeRequest)

    target: Message | None = None
    if body.message_id is not None:
        target = db.session.get(Message, body.message_id)
        if target is None or target.conversation_id != conversation.id:
            raise NotFoundError(
                f"Message {body.message_id} does not belong to conversation {conversation_id}."
            )
        if target.sender_type != SenderType.CUSTOMER:
            raise ValidationFailed("Only customer messages can be analysed.")
    else:
        target = conversation.latest_customer_message

    if target is None:
        raise ValidationFailed("This conversation contains no customer message to analyse.")

    # Duplicate-request guard: re-analysing costs money and creates a second
    # audit trail, so it must be an explicit choice.
    existing = next(
        (
            analysis
            for analysis in conversation.analyses
            if analysis.message_id == target.id
        ),
        None,
    )
    if existing and not body.force:
        raise ConflictError(
            "This message has already been analysed. Send {\"force\": true} to re-run.",
            details={"existing_analysis_id": existing.id},
        )

    pipeline = get_pipeline()
    analysis = pipeline.analyze_conversation(conversation, message=target)

    return (
        jsonify(
            {
                "analysis": analysis.to_dict(),
                "conversation": conversation.to_dict(include_messages=True),
                "tasks": [task.to_dict() for task in conversation.tasks],
            }
        ),
        201,
    )
