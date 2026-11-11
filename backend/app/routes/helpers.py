"""Shared helpers for route modules."""

from __future__ import annotations

from typing import TypeVar

from flask import current_app, request
from pydantic import BaseModel, ValidationError

from ..services.ai.factory import AIStack
from ..services.rag.retriever import KnowledgeRetriever
from ..services.workflows.pipeline import AnalysisPipeline
from ..utils.errors import ValidationFailed

ModelT = TypeVar("ModelT", bound=BaseModel)


def parse_body(schema: type[ModelT]) -> ModelT:
    """Validate the JSON body against a Pydantic schema, or raise a 422."""
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValidationFailed("Request body must be a JSON object.")
    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        raise ValidationFailed(
            "Request payload is invalid.",
            details=[
                {
                    "field": ".".join(str(part) for part in error["loc"]) or "body",
                    "message": error["msg"],
                }
                for error in exc.errors()
            ],
        ) from exc


def get_ai_stack() -> AIStack:
    return current_app.extensions["ai_stack"]


def get_pipeline() -> AnalysisPipeline:
    return current_app.extensions["analysis_pipeline"]


def get_retriever() -> KnowledgeRetriever:
    return get_pipeline().retriever


def int_arg(name: str, default: int, *, minimum: int = 1, maximum: int = 200) -> int:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationFailed(f"Query parameter '{name}' must be an integer.") from exc
    return max(minimum, min(value, maximum))
