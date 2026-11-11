"""Audit trail helper.

One function, used everywhere, so the audit log cannot drift into
inconsistent shapes. Callers commit; this only stages the row, which keeps
audit records inside the same transaction as the thing they describe.
"""

from __future__ import annotations

import logging
from typing import Any

from ..extensions import db
from ..models import AuditAction, AuditLog
from ..utils.request_context import current_request_id

logger = logging.getLogger(__name__)

# Keys that must never appear in an audit metadata blob.
_FORBIDDEN_KEYS = {"content", "message", "raw_message", "suggested_response", "password"}


def _sanitise(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    return {
        key: value
        for key, value in metadata.items()
        if key not in _FORBIDDEN_KEYS
    }


def record_audit(
    action: AuditAction,
    *,
    entity_type: str,
    entity_id: int | None = None,
    actor: str = "system",
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        request_id=current_request_id(),
        audit_metadata=_sanitise(metadata),
    )
    db.session.add(entry)
    logger.info(
        "audit action=%s entity=%s:%s actor=%s", action.value, entity_type, entity_id, actor
    )
    return entry
