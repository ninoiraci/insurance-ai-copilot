"""Operational models: work items produced by the workflow, and the audit trail."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import JSONColumn, Model, TimestampMixin, enum_column, utcnow
from .enums import AuditAction, TaskPriority, TaskStatus, Team


class Task(Model, TimestampMixin):
    """A concrete unit of human work created by the next-best-action engine."""

    __tablename__ = "tasks"

    customer_id: Mapped[int] = mapped_column(
        sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    # Which analysis produced this task. Without it, approving one draft could
    # not tell its own work item apart from those of earlier analyses on the
    # same conversation (re-running analysis creates a second task).
    ai_analysis_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("ai_analyses.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    assigned_team: Mapped[Team] = mapped_column(
        enum_column(Team), default=Team.UNASSIGNED, nullable=False, index=True
    )
    priority: Mapped[TaskPriority] = mapped_column(
        enum_column(TaskPriority), default=TaskPriority.MEDIUM, nullable=False
    )
    status: Mapped[TaskStatus] = mapped_column(
        enum_column(TaskStatus), default=TaskStatus.OPEN, nullable=False, index=True
    )
    due_at: Mapped[datetime | None] = mapped_column(sa.DateTime)
    source: Mapped[str] = mapped_column(sa.String(40), default="AI_WORKFLOW", nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="tasks")  # noqa: F821
    conversation: Mapped["Conversation | None"] = relationship(  # noqa: F821
        back_populates="tasks"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "conversation_id": self.conversation_id,
            "ai_analysis_id": self.ai_analysis_id,
            "title": self.title,
            "description": self.description,
            "assigned_team": self.assigned_team.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
        }


class AuditLog(Model):
    """Append-only record of everything the system decided or a human approved."""

    __tablename__ = "audit_logs"

    action: Mapped[AuditAction] = mapped_column(
        enum_column(AuditAction), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(sa.String(60), nullable=False, index=True)
    entity_id: Mapped[int | None] = mapped_column(sa.Integer, index=True)
    actor: Mapped[str] = mapped_column(sa.String(80), default="system", nullable=False)
    request_id: Mapped[str | None] = mapped_column(sa.String(40), index=True)
    # Deliberately never contains raw customer message bodies - see
    # docs/SECURITY_AND_LIMITATIONS.md.
    audit_metadata: Mapped[dict] = mapped_column("metadata", JSONColumn, default=dict)
    timestamp: Mapped[datetime] = mapped_column(
        sa.DateTime, default=utcnow, nullable=False, index=True
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "action": self.action.value,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "actor": self.actor,
            "request_id": self.request_id,
            "metadata": self.audit_metadata or {},
            "timestamp": self.timestamp.isoformat(),
        }
