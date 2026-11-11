"""SQLAlchemy models. Import everything here so Alembic sees the metadata."""

from .ai import AIAnalysis, HumanReview
from .base import EMBEDDING_DIMENSIONS, Model, utcnow
from .conversation import Conversation, Message
from .customer import Customer, Policy
from .enums import (
    ACTION_TO_TEAM,
    HIGH_RISK_INTENTS,
    LOW_RISK_INTENTS,
    AuditAction,
    Channel,
    ConversationStatus,
    InsuranceType,
    Intent,
    PolicyStatus,
    RecommendedAction,
    ReviewerAction,
    SenderType,
    TaskPriority,
    TaskStatus,
    Team,
    Urgency,
)
from .evaluation import EvaluationCase, EvaluationResult, EvaluationRun
from .knowledge import KnowledgeChunk, KnowledgeDocument
from .operations import AuditLog, Task

__all__ = [
    "ACTION_TO_TEAM",
    "AIAnalysis",
    "AuditAction",
    "AuditLog",
    "Channel",
    "Conversation",
    "ConversationStatus",
    "Customer",
    "EMBEDDING_DIMENSIONS",
    "EvaluationCase",
    "EvaluationResult",
    "EvaluationRun",
    "HIGH_RISK_INTENTS",
    "HumanReview",
    "InsuranceType",
    "Intent",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "LOW_RISK_INTENTS",
    "Message",
    "Model",
    "Policy",
    "PolicyStatus",
    "RecommendedAction",
    "ReviewerAction",
    "SenderType",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "Team",
    "Urgency",
    "utcnow",
]
