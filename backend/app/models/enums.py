"""Controlled vocabularies shared by the database, the AI schemas and the API.

Single source of truth: the LLM prompt, the Pydantic validator, the SQLAlchemy
columns and the frontend TypeScript types are all generated from (or checked
against) these enums. A model that invents a label outside this taxonomy fails
validation instead of silently polluting the database.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """Python 3.10 compatible string enum with a helpful `values()` helper."""

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]

    @classmethod
    def coerce(cls, raw: object, default: "StrEnum | None" = None):
        """Best-effort parse; returns `default` instead of raising."""
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, str):
            candidate = raw.strip().upper().replace(" ", "_").replace("-", "_")
            try:
                return cls(candidate)
            except ValueError:
                return default
        return default

    def __str__(self) -> str:  # keeps f-strings and JSON clean
        return self.value


class Intent(StrEnum):
    CLAIM = "CLAIM"
    RENEWAL = "RENEWAL"
    NEW_QUOTE = "NEW_QUOTE"
    PAYMENT = "PAYMENT"
    DOCUMENT_REQUEST = "DOCUMENT_REQUEST"
    POLICY_INFORMATION = "POLICY_INFORMATION"
    POLICY_CHANGE = "POLICY_CHANGE"
    CANCELLATION = "CANCELLATION"
    COMPLAINT = "COMPLAINT"
    CROSS_SELL = "CROSS_SELL"
    GENERAL_SUPPORT = "GENERAL_SUPPORT"
    UNKNOWN = "UNKNOWN"


class InsuranceType(StrEnum):
    MOTOR = "MOTOR"
    HOME = "HOME"
    LIFE = "LIFE"
    HEALTH = "HEALTH"
    TRAVEL = "TRAVEL"
    BUSINESS = "BUSINESS"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class Urgency(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}[self.value]

    @classmethod
    def max(cls, *levels: "Urgency") -> "Urgency":
        return max(levels, key=lambda level: level.rank)


class RecommendedAction(StrEnum):
    REQUEST_DOCUMENTS = "REQUEST_DOCUMENTS"
    CREATE_CLAIM_CASE = "CREATE_CLAIM_CASE"
    ASSIGN_TO_CLAIMS = "ASSIGN_TO_CLAIMS"
    ASSIGN_TO_SALES = "ASSIGN_TO_SALES"
    ASSIGN_TO_ADMIN = "ASSIGN_TO_ADMIN"
    SCHEDULE_FOLLOW_UP = "SCHEDULE_FOLLOW_UP"
    SEND_POLICY_INFORMATION = "SEND_POLICY_INFORMATION"
    PREPARE_QUOTE = "PREPARE_QUOTE"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
    RENEWAL_CONTACT = "RENEWAL_CONTACT"
    CANCELLATION_WORKFLOW = "CANCELLATION_WORKFLOW"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"
    NO_ACTION = "NO_ACTION"


class Team(StrEnum):
    CLAIMS_TEAM = "CLAIMS_TEAM"
    SALES_TEAM = "SALES_TEAM"
    ADMIN_TEAM = "ADMIN_TEAM"
    CUSTOMER_SUCCESS = "CUSTOMER_SUCCESS"
    COMPLIANCE_TEAM = "COMPLIANCE_TEAM"
    UNASSIGNED = "UNASSIGNED"


class Channel(StrEnum):
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    PHONE_CALL = "PHONE_CALL"


class SenderType(StrEnum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class ConversationStatus(StrEnum):
    NEW = "NEW"
    AI_PROCESSED = "AI_PROCESSED"
    PENDING_REVIEW = "PENDING_REVIEW"
    AWAITING_CUSTOMER = "AWAITING_CUSTOMER"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class PolicyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    LAPSED = "LAPSED"
    CANCELLED = "CANCELLED"
    PENDING_RENEWAL = "PENDING_RENEWAL"


class TaskStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class TaskPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReviewerAction(StrEnum):
    APPROVE = "APPROVE"
    EDIT_AND_APPROVE = "EDIT_AND_APPROVE"
    REJECT = "REJECT"


class AuditAction(StrEnum):
    AI_ANALYSIS_CREATED = "AI_ANALYSIS_CREATED"
    AI_ANALYSIS_FAILED = "AI_ANALYSIS_FAILED"
    AI_OUTPUT_VALIDATION_FAILED = "AI_OUTPUT_VALIDATION_FAILED"
    BUSINESS_RULE_OVERRIDE = "BUSINESS_RULE_OVERRIDE"
    PROMPT_INJECTION_SUSPECTED = "PROMPT_INJECTION_SUSPECTED"
    HUMAN_REVIEW_RECORDED = "HUMAN_REVIEW_RECORDED"
    RESPONSE_SIMULATED_SEND = "RESPONSE_SIMULATED_SEND"
    TASK_CREATED = "TASK_CREATED"
    KNOWLEDGE_INGESTED = "KNOWLEDGE_INGESTED"
    KNOWLEDGE_SEARCHED = "KNOWLEDGE_SEARCHED"
    EVALUATION_RUN = "EVALUATION_RUN"


# Mapping used by the deterministic action engine to route work to a team.
ACTION_TO_TEAM: dict[RecommendedAction, Team] = {
    RecommendedAction.REQUEST_DOCUMENTS: Team.CLAIMS_TEAM,
    RecommendedAction.CREATE_CLAIM_CASE: Team.CLAIMS_TEAM,
    RecommendedAction.ASSIGN_TO_CLAIMS: Team.CLAIMS_TEAM,
    RecommendedAction.ASSIGN_TO_SALES: Team.SALES_TEAM,
    RecommendedAction.ASSIGN_TO_ADMIN: Team.ADMIN_TEAM,
    RecommendedAction.SCHEDULE_FOLLOW_UP: Team.CUSTOMER_SUCCESS,
    RecommendedAction.SEND_POLICY_INFORMATION: Team.CUSTOMER_SUCCESS,
    RecommendedAction.PREPARE_QUOTE: Team.SALES_TEAM,
    RecommendedAction.ESCALATE_TO_HUMAN: Team.COMPLIANCE_TEAM,
    RecommendedAction.RENEWAL_CONTACT: Team.SALES_TEAM,
    RecommendedAction.CANCELLATION_WORKFLOW: Team.ADMIN_TEAM,
    RecommendedAction.REQUEST_CLARIFICATION: Team.CUSTOMER_SUCCESS,
    RecommendedAction.NO_ACTION: Team.UNASSIGNED,
}

# Intents where a wrong or hallucinated answer has real financial, legal or
# reputational consequences. These always go through a human.
HIGH_RISK_INTENTS: frozenset[Intent] = frozenset(
    {
        Intent.CLAIM,
        Intent.COMPLAINT,
        Intent.CANCELLATION,
        Intent.PAYMENT,
    }
)

# Intents where a grounded, low-risk answer may be auto-approval eligible.
LOW_RISK_INTENTS: frozenset[Intent] = frozenset(
    {
        Intent.POLICY_INFORMATION,
        Intent.DOCUMENT_REQUEST,
        Intent.GENERAL_SUPPORT,
    }
)
