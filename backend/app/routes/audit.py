"""Audit log browsing."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from ..extensions import db
from ..models import AuditAction, AuditLog
from ..utils.errors import ValidationFailed
from .helpers import int_arg

bp = Blueprint("audit", __name__, url_prefix="/api/audit-logs")


@bp.get("")
def list_audit_logs():
    limit = int_arg("limit", 100, maximum=500)
    action_raw = request.args.get("action")
    entity_type = request.args.get("entity_type")

    statement = select(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())

    if action_raw:
        action = AuditAction.coerce(action_raw)
        if action is None:
            raise ValidationFailed(
                f"Invalid action '{action_raw}'. Allowed: {', '.join(AuditAction.values())}."
            )
        statement = statement.where(AuditLog.action == action)

    if entity_type:
        statement = statement.where(AuditLog.entity_type == entity_type)

    logs = db.session.execute(statement.limit(limit)).scalars().all()
    return jsonify(
        {
            "items": [log.to_dict() for log in logs],
            "count": len(logs),
            "actions": AuditAction.values(),
        }
    )
