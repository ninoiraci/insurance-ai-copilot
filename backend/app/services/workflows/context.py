"""Customer 360 context assembly.

Two competing goals:

* the model needs enough business state to be useful (an expiring policy
  changes the urgency of a payment failure);
* the prompt must not become a dump of the database - irrelevant context costs
  tokens, dilutes attention and widens the blast radius of a prompt injection.

So we select deliberately: active policies, a handful of recent interactions,
open tasks. Never other customers, never raw internal notes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ...models import (
    Conversation,
    Customer,
    InsuranceType,
    Policy,
    PolicyStatus,
    Task,
    TaskStatus,
)

MAX_POLICIES = 6
MAX_RECENT_CONVERSATIONS = 4
MAX_OPEN_TASKS = 4


@dataclass
class CustomerContext:
    customer_id: int
    full_name: str
    preferred_language: str
    policies: list[dict] = field(default_factory=list)
    recent_interactions: list[dict] = field(default_factory=list)
    open_tasks: list[dict] = field(default_factory=list)

    @property
    def soonest_expiring_policy(self) -> dict | None:
        active = [policy for policy in self.policies if policy["status"] == "ACTIVE"]
        if not active:
            return None
        return min(active, key=lambda policy: policy["days_to_expiration"])

    def policy_for_type(self, insurance_type: InsuranceType) -> dict | None:
        for policy in self.policies:
            if policy["policy_type"] == insurance_type.value:
                return policy
        return None

    def to_prompt_block(self) -> str:
        """Compact, human-readable context. Markdown, because models read it well."""
        lines = [
            f"Customer: {self.full_name} (id {self.customer_id})",
            f"Preferred language: {self.preferred_language}",
        ]

        if self.policies:
            lines.append("Active policies:")
            for policy in self.policies:
                extra = ""
                if policy.get("vehicle_plate"):
                    extra = f", plate {policy['vehicle_plate']}"
                lines.append(
                    f"  - {policy['policy_type']} {policy['policy_number']} "
                    f"({policy['provider']}), status {policy['status']}, "
                    f"expires {policy['expiration_date']} "
                    f"[{policy['days_to_expiration']} days]{extra}"
                )
        else:
            lines.append("Active policies: none on record")

        if self.recent_interactions:
            lines.append("Recent interactions:")
            for interaction in self.recent_interactions:
                lines.append(
                    f"  - {interaction['date']} via {interaction['channel']}: "
                    f"{interaction['subject']}"
                )

        if self.open_tasks:
            lines.append("Open tasks:")
            for task in self.open_tasks:
                lines.append(f"  - [{task['priority']}] {task['title']} ({task['team']})")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "full_name": self.full_name,
            "preferred_language": self.preferred_language,
            "policies": self.policies,
            "recent_interactions": self.recent_interactions,
            "open_tasks": self.open_tasks,
        }


def build_customer_context(
    customer: Customer,
    *,
    exclude_conversation_id: int | None = None,
    today: date | None = None,
) -> CustomerContext:
    reference = today or date.today()

    relevant_policies: list[Policy] = sorted(
        [
            policy
            for policy in customer.policies
            if policy.status in {PolicyStatus.ACTIVE, PolicyStatus.PENDING_RENEWAL}
        ],
        key=lambda policy: policy.expiration_date,
    )[:MAX_POLICIES]

    recent: list[Conversation] = sorted(
        [
            conversation
            for conversation in customer.conversations
            if conversation.id != exclude_conversation_id
        ],
        key=lambda conversation: conversation.created_at,
        reverse=True,
    )[:MAX_RECENT_CONVERSATIONS]

    open_tasks: list[Task] = [
        task
        for task in customer.tasks
        if task.status in {TaskStatus.OPEN, TaskStatus.IN_PROGRESS}
    ][:MAX_OPEN_TASKS]

    return CustomerContext(
        customer_id=customer.id,
        full_name=customer.full_name,
        preferred_language=customer.preferred_language,
        policies=[
            {
                "policy_number": policy.policy_number,
                "policy_type": policy.policy_type.value,
                "provider": policy.provider,
                "status": policy.status.value,
                "expiration_date": policy.expiration_date.isoformat(),
                "days_to_expiration": policy.days_to_expiration(reference),
                "vehicle_plate": policy.vehicle_plate,
            }
            for policy in relevant_policies
        ],
        recent_interactions=[
            {
                "date": conversation.created_at.date().isoformat(),
                "channel": conversation.channel.value,
                "subject": conversation.subject,
                "status": conversation.status.value,
            }
            for conversation in recent
        ],
        open_tasks=[
            {
                "title": task.title,
                "priority": task.priority.value,
                "team": task.assigned_team.value,
            }
            for task in open_tasks
        ],
    )
