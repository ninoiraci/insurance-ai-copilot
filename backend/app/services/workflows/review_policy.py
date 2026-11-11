"""Human-in-the-loop gate.

This is the last decision before a draft becomes visible as "ready to send".
It is intentionally conservative and intentionally *not* AI: whether a human
must look at something is a governance rule, so it is expressed as code that
can be read, tested and signed off.

Auto-approval eligibility is narrow by construction. Everything else requires
a human, and the reasons are stored so the operator sees why.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...models import HIGH_RISK_INTENTS, LOW_RISK_INTENTS, Intent, Urgency
from ...schemas.ai_output import GeneratedResponse, MessageAnalysis
from .action_engine import ActionDecision
from .business_rules import BusinessRuleResult


@dataclass
class ReviewDecision:
    required: bool
    reasons: list[str] = field(default_factory=list)
    auto_approval_eligible: bool = False

    def to_dict(self) -> dict:
        return {
            "human_review_required": self.required,
            "reasons": self.reasons,
            "auto_approval_eligible": self.auto_approval_eligible,
        }


def decide_review(
    analysis: MessageAnalysis,
    rules: BusinessRuleResult,
    action: ActionDecision,
    response: GeneratedResponse | None,
    *,
    confidence_threshold: float,
    demo_mode: bool,
) -> ReviewDecision:
    reasons: list[str] = []

    if analysis.intent in HIGH_RISK_INTENTS:
        reasons.append(
            f"{analysis.intent.value} is a high-risk intent (financial, legal or "
            "reputational consequences)."
        )

    if rules.urgency.rank >= Urgency.HIGH.rank:
        reasons.append(f"Urgency is {rules.urgency.value}.")

    if analysis.confidence < confidence_threshold:
        reasons.append(
            f"Confidence {analysis.confidence:.2f} is below the threshold "
            f"{confidence_threshold:.2f}."
        )

    if analysis.intent == Intent.UNKNOWN:
        reasons.append("Intent could not be determined.")

    if rules.safety_flags:
        reasons.extend(f"Safety flag: {flag}." for flag in rules.safety_flags)

    if action.human_review_required:
        reasons.append("The next-best-action engine requires human sign-off for this action.")

    if response is None:
        reasons.append("No response draft could be generated.")
    else:
        if response.insufficient_information:
            reasons.append(
                "The knowledge base did not support a reliable answer; the draft is a "
                "holding reply only."
            )
        if not response.grounded:
            reasons.append("The draft is not grounded in retrieved documentation.")

    # Demo mode deliberately does NOT add a review reason. `required` measures
    # the governance policy itself, which must be comparable between demo and
    # real-LLM evaluation runs. Demo mode instead removes auto-approval
    # eligibility outright, which is the control that actually matters.
    eligible = (
        not reasons
        and not demo_mode
        and analysis.intent in LOW_RISK_INTENTS
        and analysis.confidence >= confidence_threshold
        and rules.urgency.rank <= Urgency.MEDIUM.rank
        and response is not None
        and response.grounded
        and not response.insufficient_information
    )

    return ReviewDecision(
        required=bool(reasons),
        reasons=reasons,
        auto_approval_eligible=eligible,
    )
