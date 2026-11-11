"""AI analysis retrieval and the human-in-the-loop review endpoint."""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..extensions import db
from ..models import AIAnalysis
from ..schemas.api import ReviewRequest
from ..services.workflows.review_service import record_review
from ..utils.errors import ConflictError, NotFoundError, ValidationFailed
from .helpers import parse_body

bp = Blueprint("analyses", __name__, url_prefix="/api/analyses")


@bp.get("/<int:analysis_id>")
def get_analysis(analysis_id: int):
    analysis = db.session.get(AIAnalysis, analysis_id)
    if analysis is None:
        raise NotFoundError(f"Analysis {analysis_id} does not exist.")
    return jsonify(analysis.to_dict())


@bp.post("/<int:analysis_id>/review")
def review_analysis(analysis_id: int):
    analysis = db.session.get(AIAnalysis, analysis_id)
    if analysis is None:
        raise NotFoundError(f"Analysis {analysis_id} does not exist.")

    body = parse_body(ReviewRequest)

    if analysis.latest_review is not None:
        raise ConflictError(
            "This analysis has already been reviewed.",
            details={"existing_review": analysis.latest_review.to_dict()},
        )

    try:
        review = record_review(analysis, body)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc

    return (
        jsonify(
            {
                "review": review.to_dict(),
                "analysis": analysis.to_dict(),
                "note": (
                    "No message was sent. This proof of concept records the approval "
                    "decision only (simulated send)."
                ),
            }
        ),
        201,
    )
