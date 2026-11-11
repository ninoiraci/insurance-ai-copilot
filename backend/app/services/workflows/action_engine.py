"""Next-best-action engine.

The LLM proposes; this engine decides. It combines the model's classification
with customer state, urgency and completeness of information, and produces a
concrete, routable decision:

    action + owning team + follow-up SLA + reason

The reason string is not decoration - it is what the operator reads in the UI
to understand why the system wants what it wants, and what an auditor reads
six months later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ...models import (
    ACTION_TO_TEAM,
    Intent,
    RecommendedAction,
    Team,
    Urgency,
)
from ...schemas.ai_output import MessageAnalysis
from .business_rules import BusinessRuleResult
from .context import CustomerContext

logger = logging.getLogger(__name__)

# Follow-up SLA in hours, by urgency. Business configuration, not model output.
FOLLOW_UP_HOURS: dict[Urgency, int] = {
    Urgency.CRITICAL: 1,
    Urgency.HIGH: 4,
    Urgency.MEDIUM: 12,
    Urgency.LOW: 48,
}

# Confidence below which we stop trusting the classification enough to route on it.
ROUTING_CONFIDENCE_FLOOR = 0.45


@dataclass
class ActionDecision:
    recommended_action: RecommendedAction
    assign_to: Team
    follow_up_hours: int
    human_review_required: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "recommended_action": self.recommended_action.value,
            "assign_to": self.assign_to.value,
            "follow_up_hours": self.follow_up_hours,
            "human_review_required": self.human_review_required,
            "reason": self.reason,
        }


def decide_action(
    analysis: MessageAnalysis,
    rules: BusinessRuleResult,
    context: CustomerContext | None,
) -> ActionDecision:
    urgency = rules.urgency
    follow_up = FOLLOW_UP_HOURS[urgency]

    # 1. Safety and confidence gates come before any business routing.
    if "PROMPT_INJECTION_SUSPECTED" in rules.safety_flags:
        return ActionDecision(
            recommended_action=RecommendedAction.ESCALATE_TO_HUMAN,
            assign_to=Team.COMPLIANCE_TEAM,
            follow_up_hours=follow_up,
            human_review_required=True,
            reason=(
                "The message contains instructions aimed at the AI system rather than an "
                "insurance request. No automated action taken; routed for human inspection."
            ),
        )

    if analysis.confidence < ROUTING_CONFIDENCE_FLOOR or analysis.intent == Intent.UNKNOWN:
        return ActionDecision(
            recommended_action=RecommendedAction.REQUEST_CLARIFICATION,
            assign_to=Team.CUSTOMER_SUCCESS,
            follow_up_hours=follow_up,
            human_review_required=True,
            reason=(
                f"Classification confidence {analysis.confidence:.2f} is below the routing "
                f"floor of {ROUTING_CONFIDENCE_FLOOR:.2f}. The system asks for clarification "
                "instead of guessing an intent."
            ),
        )

    # 2. Intent-specific routing, refined by customer state.
    decision = _route_by_intent(analysis, rules, context, follow_up)

    # 3. Critical urgency always adds a human escalation on top of the action.
    if urgency == Urgency.CRITICAL and decision.recommended_action not in {
        RecommendedAction.ESCALATE_TO_HUMAN,
        RecommendedAction.CREATE_CLAIM_CASE,
    }:
        return ActionDecision(
            recommended_action=RecommendedAction.ESCALATE_TO_HUMAN,
            assign_to=Team.CLAIMS_TEAM,
            follow_up_hours=FOLLOW_UP_HOURS[Urgency.CRITICAL],
            human_review_required=True,
            reason=(
                "Urgency is CRITICAL: "
                + (rules.overrides[0].reason if rules.overrides else "escalated by policy.")
            ),
        )

    return decision


def _route_by_intent(
    analysis: MessageAnalysis,
    rules: BusinessRuleResult,
    context: CustomerContext | None,
    follow_up: int,
) -> ActionDecision:
    intent = analysis.intent
    missing = analysis.missing_information
    urgency = rules.urgency

    if intent == Intent.CLAIM:
        if missing:
            return ActionDecision(
                recommended_action=RecommendedAction.REQUEST_DOCUMENTS,
                assign_to=Team.CLAIMS_TEAM,
                follow_up_hours=follow_up,
                human_review_required=True,
                reason=(
                    f"{analysis.insurance_type.value} incident reported, but mandatory claim "
                    f"information is missing: {', '.join(missing[:3])}."
                ),
            )
        return ActionDecision(
            recommended_action=RecommendedAction.CREATE_CLAIM_CASE,
            assign_to=Team.CLAIMS_TEAM,
            follow_up_hours=follow_up,
            human_review_required=True,
            reason="Incident reported with all mandatory information present; open a claim file.",
        )

    if intent == Intent.COMPLAINT:
        return ActionDecision(
            recommended_action=RecommendedAction.ESCALATE_TO_HUMAN,
            assign_to=Team.COMPLIANCE_TEAM,
            follow_up_hours=follow_up,
            human_review_required=True,
            reason="Complaints are escalated to a named owner within the regulatory window.",
        )

    if intent == Intent.CANCELLATION:
        return ActionDecision(
            recommended_action=RecommendedAction.CANCELLATION_WORKFLOW,
            assign_to=Team.ADMIN_TEAM,
            follow_up_hours=follow_up,
            human_review_required=True,
            reason=(
                "Cancellation requested. Notice periods and retention outreach are handled "
                "by administration, never automatically."
            ),
        )

    if intent == Intent.PAYMENT:
        return ActionDecision(
            recommended_action=RecommendedAction.ASSIGN_TO_ADMIN,
            assign_to=Team.ADMIN_TEAM,
            follow_up_hours=follow_up,
            human_review_required=True,
            reason=(
                "Payment issue routed to administration"
                + (
                    "; coverage is at risk, treat as priority."
                    if urgency.rank >= Urgency.HIGH.rank
                    else "."
                )
            ),
        )

    if intent == Intent.RENEWAL:
        policy = context.policy_for_type(analysis.insurance_type) if context else None
        days = policy["days_to_expiration"] if policy else None
        return ActionDecision(
            recommended_action=RecommendedAction.RENEWAL_CONTACT,
            assign_to=Team.SALES_TEAM,
            follow_up_hours=follow_up,
            human_review_required=urgency.rank >= Urgency.HIGH.rank,
            reason=(
                f"Renewal enquiry for a policy expiring in {days} days."
                if days is not None
                else "Renewal enquiry; no matching active policy found on record."
            ),
        )

    if intent in {Intent.NEW_QUOTE, Intent.CROSS_SELL}:
        return ActionDecision(
            recommended_action=RecommendedAction.PREPARE_QUOTE,
            assign_to=Team.SALES_TEAM,
            follow_up_hours=follow_up,
            human_review_required=bool(missing),
            reason=(
                "Sales opportunity; prepare a quote."
                + (f" Still needed: {', '.join(missing[:3])}." if missing else "")
            ),
        )

    if intent == Intent.POLICY_CHANGE:
        return ActionDecision(
            recommended_action=RecommendedAction.ASSIGN_TO_ADMIN,
            assign_to=Team.ADMIN_TEAM,
            follow_up_hours=follow_up,
            human_review_required=True,
            reason="Policy modification requires an endorsement issued by administration.",
        )

    if intent in {Intent.POLICY_INFORMATION, Intent.DOCUMENT_REQUEST}:
        return ActionDecision(
            recommended_action=RecommendedAction.SEND_POLICY_INFORMATION,
            assign_to=Team.CUSTOMER_SUCCESS,
            follow_up_hours=follow_up,
            # Review requirement is finalised by the review policy, which also
            # checks grounding. Here we only express the routing default.
            human_review_required=False,
            reason="Informational request that can be answered from the knowledge base.",
        )

    return ActionDecision(
        recommended_action=RecommendedAction.REQUEST_CLARIFICATION,
        assign_to=ACTION_TO_TEAM[RecommendedAction.REQUEST_CLARIFICATION],
        follow_up_hours=follow_up,
        human_review_required=True,
        reason="No specific workflow matches this message; a human should read it.",
    )
