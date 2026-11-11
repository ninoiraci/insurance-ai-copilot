"""Evaluation dataset, runs and metrics."""

from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import func, select

from ..extensions import db
from ..models import EvaluationCase, EvaluationRun
from ..schemas.api import EvaluationRunRequest
from ..services.evaluation.runner import run_evaluation
from ..utils.errors import NotFoundError, ValidationFailed
from .helpers import get_pipeline, int_arg, parse_body

bp = Blueprint("evaluations", __name__, url_prefix="/api/evaluations")


@bp.get("")
def list_runs():
    limit = int_arg("limit", 20, maximum=100)
    runs = (
        db.session.execute(
            select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(limit)
        )
        .scalars()
        .all()
    )
    case_count = db.session.scalar(select(func.count(EvaluationCase.id))) or 0
    return jsonify(
        {
            "items": [run.to_dict() for run in runs],
            "count": len(runs),
            "dataset_size": case_count,
            "latest": runs[0].to_dict(include_results=True) if runs else None,
        }
    )


@bp.get("/<int:run_id>")
def get_run(run_id: int):
    run = db.session.get(EvaluationRun, run_id)
    if run is None:
        raise NotFoundError(f"Evaluation run {run_id} does not exist.")
    return jsonify(run.to_dict(include_results=True))


@bp.post("/run")
def trigger_run():
    body = parse_body(EvaluationRunRequest)
    try:
        run = run_evaluation(get_pipeline(), label=body.label, limit=body.limit)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
    return jsonify(run.to_dict(include_results=True)), 201
