"""Conversation and message models - the multi-channel inbox."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Model, enum_column, utcnow
from .enums import Channel, ConversationStatus, SenderType, Team


class Conversation(Model):
    __tablename__ = "conversations"

    customer_id: Mapped[int] = mapped_column(
        sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[Channel] = mapped_column(enum_column(Channel), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    status: Mapped[ConversationStatus] = mapped_column(
        enum_column(ConversationStatus),
        default=ConversationStatus.NEW,
        nullable=False,
        index=True,
    )
    assigned_team: Mapped[Team] = mapped_column(
        enum_column(Team), default=Team.UNASSIGNED, nullable=False, index=True
    )
    # Stable key so the seed script is idempotent and demo cases are addressable.
    reference: Mapped[str | None] = mapped_column(sa.String(40), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime, default=utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    customer: Mapped["Customer"] = relationship(back_populates="conversations")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.timestamp",
    )
    analyses: Mapped[list["AIAnalysis"]] = relationship(  # noqa: F821
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIAnalysis.created_at",
    )
    tasks: Mapped[list["Task"]] = relationship(  # noqa: F821
        back_populates="conversation", cascade="all, delete-orphan"
    )

    @property
    def latest_customer_message(self) -> "Message | None":
        for message in reversed(self.messages):
            if message.sender_type == SenderType.CUSTOMER:
                return message
        return None

    @property
    def latest_analysis(self) -> "AIAnalysis | None":  # noqa: F821
        return self.analyses[-1] if self.analyses else None

    def to_dict(self, *, include_messages: bool = False) -> dict:
        analysis = self.latest_analysis
        payload = {
            "id": self.id,
            "reference": self.reference,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "channel": self.channel.value,
            "subject": self.subject,
            "status": self.status.value,
            "assigned_team": self.assigned_team.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "message_count": len(self.messages),
            "latest_analysis": analysis.to_summary_dict() if analysis else None,
        }
        if include_messages:
            payload["messages"] = [message.to_dict() for message in self.messages]
        else:
            latest = self.latest_customer_message
            payload["preview"] = (latest.content[:160] if latest else "")
        return payload


class Message(Model):
    __tablename__ = "messages"

    conversation_id: Mapped[int] = mapped_column(
        sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_type: Mapped[SenderType] = mapped_column(enum_column(SenderType), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        sa.DateTime, default=utcnow, nullable=False, index=True
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "sender_type": self.sender_type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
