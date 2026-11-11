"""Customer and policy models - the business state the AI reasons about."""

from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Model, TimestampMixin, enum_column
from .enums import InsuranceType, PolicyStatus


class Customer(Model, TimestampMixin):
    __tablename__ = "customers"

    full_name: Mapped[str] = mapped_column(sa.String(160), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(sa.String(200), unique=True)
    phone: Mapped[str | None] = mapped_column(sa.String(40))
    preferred_language: Mapped[str] = mapped_column(sa.String(8), default="es", nullable=False)
    city: Mapped[str | None] = mapped_column(sa.String(80))
    notes: Mapped[str | None] = mapped_column(sa.Text)

    policies: Mapped[list["Policy"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", order_by="Policy.expiration_date"
    )
    conversations: Mapped[list["Conversation"]] = relationship(  # noqa: F821
        back_populates="customer", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(  # noqa: F821
        back_populates="customer", cascade="all, delete-orphan"
    )

    def to_dict(self, *, include_relations: bool = False) -> dict:
        payload = {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "preferred_language": self.preferred_language,
            "city": self.city,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_relations:
            payload["policies"] = [policy.to_dict() for policy in self.policies]
            payload["tasks"] = [task.to_dict() for task in self.tasks]
            payload["conversations"] = [
                conversation.to_dict() for conversation in self.conversations
            ]
        else:
            payload["policy_count"] = len(self.policies)
            payload["conversation_count"] = len(self.conversations)
            payload["open_task_count"] = sum(
                1 for task in self.tasks if task.status.value in {"OPEN", "IN_PROGRESS"}
            )
        return payload


class Policy(Model, TimestampMixin):
    __tablename__ = "policies"

    customer_id: Mapped[int] = mapped_column(
        sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_number: Mapped[str] = mapped_column(sa.String(40), unique=True, nullable=False)
    policy_type: Mapped[InsuranceType] = mapped_column(
        enum_column(InsuranceType), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    expiration_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    status: Mapped[PolicyStatus] = mapped_column(
        enum_column(PolicyStatus), default=PolicyStatus.ACTIVE, nullable=False
    )
    annual_premium: Mapped[float | None] = mapped_column(sa.Float)
    vehicle_plate: Mapped[str | None] = mapped_column(sa.String(16))
    property_address: Mapped[str | None] = mapped_column(sa.String(200))

    customer: Mapped[Customer] = relationship(back_populates="policies")

    def days_to_expiration(self, today: date | None = None) -> int:
        reference = today or datetime.utcnow().date()
        return (self.expiration_date - reference).days

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "policy_number": self.policy_number,
            "policy_type": self.policy_type.value,
            "provider": self.provider,
            "start_date": self.start_date.isoformat(),
            "expiration_date": self.expiration_date.isoformat(),
            "status": self.status.value,
            "annual_premium": self.annual_premium,
            "vehicle_plate": self.vehicle_plate,
            "property_address": self.property_address,
            "days_to_expiration": self.days_to_expiration(),
        }
