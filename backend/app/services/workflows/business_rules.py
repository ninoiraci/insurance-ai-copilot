"""Deterministic business rules applied *after* the LLM.

Why this layer exists: urgency is a business decision with operational and
legal consequences, and an LLM's notion of "urgent" is neither stable across
runs nor auditable. So the model reports what the message says, and this code
decides what the brokerage does about it.

Rules only ever **raise** urgency, never lower it. A model that under-reports
severity is corrected; a model that over-reports is left alone, because the
cost of an unnecessary escalation is far lower than a missed injury.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ...models import Intent, PolicyStatus, Urgency
from ...schemas.ai_output import MessageAnalysis
from ...utils.text import detect_injection
from .context import CustomerContext

logger = logging.getLogger(__name__)

# Thresholds are named constants, not literals buried in conditionals, so a
# business stakeholder can change them without reading the whole function.
RENEWAL_URGENT_DAYS = 7
RENEWAL_SOON_DAYS = 30
PAYMENT_RISK_DAYS = 15
CLAIM_COVERAGE_RISK_DAYS = 0


@dataclass
class RuleOutcome:
    rule: str
    from_urgency: str
    to_urgency: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "from": self.from_urgency,
            "to": self.to_urgency,
            "reason": self.reason,
        }


@dataclass
class BusinessRuleResult:
    urgency: Urgency
    overrides: list[RuleOutcome] = field(default_factory=list)
    safety_flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def override_dicts(self) -> list[dict]:
        return [override.to_dict() for override in self.overrides]


def apply_business_rules(
    analysis: MessageAnalysis,
    context: CustomerContext | None,
    *,
    raw_message: str,
) -> BusinessRuleResult:
    urgency = analysis.urgency
    result = BusinessRuleResult(urgency=urgency)
    entities = analysis.extracted_entities

    def escalate(rule: str, target: Urgency, reason: str) -> None:
        nonlocal urgency
        if target.rank > urgency.rank:
            result.overrides.append(
                RuleOutcome(rule=rule, from_urgency=urgency.value, to_urgency=target.value,
                            reason=reason)
            )
            logger.info("business_rule_override rule=%s %s -> %s", rule, urgency, target)
            urgency = target

    # --- safety signals -----------------------------------------------------
    injection_hits = detect_injection(raw_message)
    if injection_hits:
        result.safety_flags.append("PROMPT_INJECTION_SUSPECTED")
        result.notes.append(
            f"{len(injection_hits)} prompt-injection heuristic(s) matched in customer text."
        )

    # --- people first -------------------------------------------------------
    if entities.injuries is True:
        escalate(
            "injuries_reported",
            Urgency.CRITICAL,
            "Customer message indicates possible injuries.",
        )

    # --- product-state driven rules ----------------------------------------
    policy = None
    if context:
        policy = context.policy_for_type(analysis.insurance_type)

    if analysis.intent == Intent.CLAIM:
        if policy and policy["days_to_expiration"] <= CLAIM_COVERAGE_RISK_DAYS:
            escalate(
                "claim_on_expired_policy",
                Urgency.HIGH,
                "Claim reported against a policy that is already past its expiration date.",
            )
        elif urgency.rank < Urgency.MEDIUM.rank:
            escalate(
                "claim_minimum_urgency",
                Urgency.MEDIUM,
                "Any reported incident is at least MEDIUM urgency.",
            )

    if analysis.intent == Intent.PAYMENT:
        if policy and policy["status"] == PolicyStatus.LAPSED.value:
            escalate(
                "payment_on_lapsed_policy",
                Urgency.HIGH,
                "Payment issue on a policy that has already lapsed - cover may be void.",
            )
        elif policy and 0 <= policy["days_to_expiration"] <= PAYMENT_RISK_DAYS:
            escalate(
                "payment_close_to_expiry",
                Urgency.HIGH,
                f"Payment issue with {policy['days_to_expiration']} days to policy expiry - "
                "risk of coverage lapse.",
            )

    if analysis.intent == Intent.RENEWAL and policy:
        days = policy["days_to_expiration"]
        if days <= RENEWAL_URGENT_DAYS:
            escalate(
                "renewal_imminent",
                Urgency.HIGH,
                f"Policy {policy['policy_number']} expires in {days} days.",
            )
        elif days <= RENEWAL_SOON_DAYS:
            escalate(
                "renewal_approaching",
                Urgency.MEDIUM,
                f"Policy {policy['policy_number']} expires in {days} days.",
            )

    if analysis.intent == Intent.COMPLAINT:
        escalate(
            "complaint_minimum_urgency",
            Urgency.HIGH,
            "Complaints are handled at HIGH urgency by policy (regulatory response window).",
        )

    if analysis.intent == Intent.CANCELLATION and urgency.rank < Urgency.MEDIUM.rank:
        escalate(
            "cancellation_minimum_urgency",
            Urgency.MEDIUM,
            "Cancellation requests have a legal notice period and cannot sit in the queue.",
        )

    result.urgency = urgency
    return result
