"""Evaluation runner.

Runs the *same* pipeline the product uses - classification, business rules and
the action engine - against labelled cases. Evaluating only the raw LLM call
would measure the wrong thing: what ships is the whole decision system, so
that is what gets scored.

Cases are evaluated without customer context by design. It isolates message
understanding from customer-state effects; context-dependent behaviour is
covered separately by the business-rule unit tests.
"""

from __future__ import annotations

import logging
import time

from ...extensions import db
from ...models import (
    AuditAction,
    EvaluationCase,
    EvaluationResult,
    EvaluationRun,
)
from ..audit import record_audit
from ..workflows.pipeline import AnalysisPipeline
from .metrics import MetricsAccumulator

logger = logging.getLogger(__name__)


def run_evaluation(
    pipeline: AnalysisPipeline,
    *,
    label: str = "manual run",
    limit: int | None = None,
) -> EvaluationRun:
    cases = (
        db.session.query(EvaluationCase).order_by(EvaluationCase.case_key).limit(limit).all()
        if limit
        else db.session.query(EvaluationCase).order_by(EvaluationCase.case_key).all()
    )
    if not cases:
        raise ValueError(
            "No evaluation cases in the database. Run `flask seed evaluation` first."
        )

    started = time.perf_counter()
    accumulator = MetricsAccumulator()
    run = EvaluationRun(
        label=label,
        model_name=pipeline.ai.client.model_name,
        prompt_version="classification_v1",
        demo_mode=pipeline.ai.demo_mode,
        case_count=len(cases),
    )

    for case in cases:
        expected = {
            "intent": case.expected_intent.value,
            "urgency": case.expected_urgency.value,
            "insurance_type": case.expected_insurance_type.value,
            "action": case.expected_action.value,
            "entities": case.expected_entities or {},
            "expects_human_review": case.expects_human_review,
        }

        case_started = time.perf_counter()
        error: str | None = None
        schema_valid = True

        try:
            result = pipeline.run(
                raw_message=case.input_text, context=None, channel=case.channel
            )
            predicted = {
                "intent": result.analysis.intent.value,
                "urgency": result.rules.urgency.value,
                "insurance_type": result.analysis.insurance_type.value,
                "action": result.action.recommended_action.value,
                "confidence": round(result.analysis.confidence, 3),
                "entities": result.analysis.extracted_entities.as_dict(),
                "human_review_required": result.review.required,
                "grounded": result.response.grounded,
                "retrieved_chunks": len(result.retrieved),
            }
            schema_valid = not result.fallback_used
            token_usage = result.token_usage
        except Exception as exc:  # a broken case must not abort the run
            logger.exception("evaluation_case_failed case=%s", case.case_key)
            error = str(exc)[:400]
            schema_valid = False
            predicted = {"intent": "UNKNOWN", "urgency": "MEDIUM", "human_review_required": True}
            token_usage = None

        latency_ms = int((time.perf_counter() - case_started) * 1000)
        correctness = accumulator.add(
            expected=expected,
            predicted=predicted,
            latency_ms=latency_ms,
            schema_valid=schema_valid,
            token_usage=token_usage,
        )

        run.results.append(
            EvaluationResult(
                case_key=case.case_key,
                predicted=predicted,
                expected=expected,
                correctness=correctness,
                latency_ms=latency_ms,
                schema_valid=schema_valid,
                error=error,
            )
        )

    run.metrics = accumulator.to_dict()
    run.duration_ms = int((time.perf_counter() - started) * 1000)

    db.session.add(run)
    db.session.flush()
    record_audit(
        AuditAction.EVALUATION_RUN,
        entity_type="EvaluationRun",
        entity_id=run.id,
        metadata={
            "label": label,
            "cases": run.case_count,
            "intent_accuracy": run.metrics["intent_accuracy"],
            "action_accuracy": run.metrics["action_accuracy"],
            "human_review_recall_on_risky": run.metrics["human_review_recall_on_risky"],
            "demo_mode": run.demo_mode,
            "model": run.model_name,
        },
    )
    db.session.commit()

    logger.info(
        "evaluation_complete cases=%s intent_acc=%.3f action_acc=%.3f duration_ms=%s",
        run.case_count,
        run.metrics["intent_accuracy"],
        run.metrics["action_accuracy"],
        run.duration_ms,
    )
    return run
