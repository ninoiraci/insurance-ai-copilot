"""Uniform API error handling.

Every failure leaves the API in the same JSON shape:
`{"error": {"code": ..., "message": ..., "details": ...}, "request_id": ...}`
so the frontend has exactly one error path to implement.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from ..extensions import db
from .request_context import current_request_id

logger = logging.getLogger(__name__)


class APIError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"


class ValidationFailed(APIError):
    status_code = 422
    code = "validation_failed"


class ConflictError(APIError):
    status_code = 409
    code = "conflict"


class ServiceUnavailable(APIError):
    status_code = 503
    code = "service_unavailable"


def _payload(code: str, message: str, details: Any = None) -> dict:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    body["request_id"] = current_request_id()
    return body


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def _handle_api_error(exc: APIError):
        logger.warning("api_error code=%s message=%s", exc.code, exc.message)
        return jsonify(_payload(exc.code, exc.message, exc.details)), exc.status_code

    @app.errorhandler(ValidationError)
    def _handle_pydantic(exc: ValidationError):
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"]) or "body",
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return (
            jsonify(_payload("validation_failed", "Request payload is invalid.", details)),
            422,
        )

    @app.errorhandler(SQLAlchemyError)
    def _handle_db(exc: SQLAlchemyError):
        # Roll back first: a failed statement leaves the session in a state
        # where every subsequent write in this request also fails, which turns
        # one bad query into a cascade of misleading errors.
        _rollback()
        # Never leak SQL or schema details to the client.
        logger.exception("database_error")
        return jsonify(_payload("database_error", "A database error occurred.")), 500

    @app.errorhandler(HTTPException)
    def _handle_http(exc: HTTPException):
        return (
            jsonify(_payload(exc.name.lower().replace(" ", "_"), exc.description or exc.name)),
            exc.code or 500,
        )

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):
        _rollback()
        logger.exception("unhandled_error")
        return jsonify(_payload("internal_error", "An unexpected error occurred.")), 500


def _rollback() -> None:
    """Discard any pending work so the session is reusable."""
    try:
        db.session.rollback()
    except Exception:  # pragma: no cover - rollback failing is unrecoverable
        logger.exception("session_rollback_failed")
