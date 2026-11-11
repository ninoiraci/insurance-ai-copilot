"""Customer endpoints, including the Customer 360 view."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Customer
from ..services.workflows.context import build_customer_context
from ..utils.errors import NotFoundError
from .helpers import int_arg

bp = Blueprint("customers", __name__, url_prefix="/api/customers")


@bp.get("")
def list_customers():
    search = (request.args.get("search") or "").strip()
    limit = int_arg("limit", 100, maximum=500)

    # The list payload counts policies, conversations and open tasks per
    # customer; eager-load them rather than issuing three queries each.
    statement = (
        select(Customer)
        .options(
            selectinload(Customer.policies),
            selectinload(Customer.conversations),
            selectinload(Customer.tasks),
        )
        .order_by(Customer.full_name)
    )
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(
                Customer.full_name.ilike(pattern),
                Customer.email.ilike(pattern),
                Customer.phone.ilike(pattern),
                Customer.city.ilike(pattern),
            )
        )

    customers = db.session.execute(statement.limit(limit)).scalars().all()
    return jsonify(
        {
            "items": [customer.to_dict() for customer in customers],
            "count": len(customers),
        }
    )


@bp.get("/<int:customer_id>")
def get_customer(customer_id: int):
    customer = db.session.get(Customer, customer_id)
    if customer is None:
        raise NotFoundError(f"Customer {customer_id} does not exist.")

    payload = customer.to_dict(include_relations=True)
    # The same context object the AI pipeline receives - showing it in the UI
    # makes "what did the model actually know?" answerable.
    payload["ai_context"] = build_customer_context(customer).to_dict()

    analyses = [
        analysis.to_summary_dict()
        for conversation in customer.conversations
        for analysis in conversation.analyses
    ]
    payload["ai_case_history"] = sorted(
        analyses, key=lambda item: item["created_at"], reverse=True
    )
    return jsonify(payload)
