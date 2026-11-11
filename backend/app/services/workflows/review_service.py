"""Recording a human review decision.

The POC never contacts a customer. `simulated_send` records that an operator
approved a draft *for sending*, which is what the audit trail actually needs to
capture. Wiring a real channel would replace one function here.
"""

from __future__ import annotations

import logging

from ...extensions import db
from ...models import (
    AIAnalysis,
    AuditAction,
    ConversationStatus,
    HumanReview,
    ReviewerAction,
    TaskStatus,
    utcnow,
)
from ...schemas.api import ReviewRequest
from ..audit import record_audit

logger = logging.getLogger(__name__)


def record_review(analysis: AIAnalysis, request: ReviewRequest) -> HumanReview:
    final_response = request.resolved_response(analysis.suggested_response)

    review = HumanReview(
        ai_analysis_id=analysis.id,
        reviewer_action=request.action,
        reviewer_name=request.reviewer_name,
        original_response=analysis.suggested_response,
        final_response=final_response,
        reviewer_notes=request.reviewer_notes,
        simulated_send=request.action != ReviewerAction.REJECT,
    )
    db.session.add(review)

    conversation = analysis.conversation
    if request.action == ReviewerAction.REJECT:
        # A rejected draft means the case still needs a human, so it goes to
        # ESCALATED rather than back into the "AI handled it" bucket.
        conversation.status = ConversationStatus.ESCALATED
    else:
        conversation.status = ConversationStatus.AWAITING_CUSTOMER
        # Advance only the work item this analysis created. Matching on
        # conversation alone would also sweep up tasks from earlier analyses
        # (a re-run creates a second task) and from unrelated workflows.
        for task in conversation.tasks:
            if task.ai_analysis_id == analysis.id and task.status == TaskStatus.OPEN:
                task.status = TaskStatus.IN_PROGRESS

    conversation.updated_at = utcnow()
    db.session.flush()

    record_audit(
        AuditAction.HUMAN_REVIEW_RECORDED,
        entity_type="HumanReview",
        entity_id=review.id,
        actor=request.reviewer_name,
        metadata={
            "analysis_id": analysis.id,
            "conversation_id": conversation.id,
            "reviewer_action": request.action.value,
            "response_was_edited": request.action == ReviewerAction.EDIT_AND_APPROVE,
            "had_notes": bool(request.reviewer_notes),
        },
    )

    if review.simulated_send:
        record_audit(
            AuditAction.RESPONSE_SIMULATED_SEND,
            entity_type="Conversation",
            entity_id=conversation.id,
            actor=request.reviewer_name,
            metadata={
                "analysis_id": analysis.id,
                "channel": conversation.channel.value,
                # POC: no external delivery happens. This is the record of intent.
                "delivery": "SIMULATED_ONLY",
            },
        )

    db.session.commit()
    logger.info(
        "human_review analysis=%s action=%s reviewer=%s",
        analysis.id,
        request.action.value,
        request.reviewer_name,
    )
    return review
