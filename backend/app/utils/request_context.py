"""Per-request correlation ID.

Every log line and every audit row carries the same `request_id`, so an AI
decision in the database can be traced back to the exact HTTP request and its
log output. Uses a ContextVar so background/CLI code works too.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from contextvars import ContextVar

from flask import Flask, g, has_request_context, request

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

# An inbound X-Request-ID is attacker-controlled. It is written to a
# VARCHAR(40) audit column, echoed in a response header and interpolated into
# log lines, so it is restricted to a safe alphabet and length rather than
# trusted. Anything else gets a freshly generated id.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


def sanitize_request_id(raw: str | None) -> str | None:
    """Return the id if it is safe to store, log and echo; otherwise None."""
    if not raw:
        return None
    candidate = raw.strip()
    return candidate if _SAFE_REQUEST_ID.match(candidate) else None


def current_request_id() -> str:
    existing = _request_id.get()
    if existing:
        return existing
    if has_request_context() and "request_id" in g:
        return g.request_id
    return "-"


def set_request_id(value: str | None = None) -> str:
    generated = value or uuid.uuid4().hex[:12]
    _request_id.set(generated)
    return generated


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id()
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s :: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    # SQLAlchemy's INFO level dumps every statement; keep it at WARNING.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def register_request_hooks(app: Flask) -> None:
    logger = logging.getLogger("app.request")

    @app.before_request
    def _start_request() -> None:
        incoming = sanitize_request_id(request.headers.get("X-Request-ID"))
        g.request_id = set_request_id(incoming)
        g.request_started_at = time.perf_counter()

    @app.after_request
    def _finish_request(response):
        started = getattr(g, "request_started_at", None)
        duration_ms = int((time.perf_counter() - started) * 1000) if started else -1
        response.headers["X-Request-ID"] = current_request_id()
        if request.path.startswith("/api"):
            logger.info(
                "%s %s -> %s (%sms)",
                request.method,
                request.path,
                response.status_code,
                duration_ms,
            )
        return response
