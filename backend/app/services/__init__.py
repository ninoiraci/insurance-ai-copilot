"""Service layer: all business logic lives here, never in route handlers."""

from .audit import record_audit

__all__ = ["record_audit"]
