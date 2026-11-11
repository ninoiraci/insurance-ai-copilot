"""Evaluation metrics and the evaluation runner."""

from __future__ import annotations

import pytest

from app.extensions import db
from app.models import (
    AuditAction,
    AuditLog,
    EvaluationCase,
    EvaluationRun,
    InsuranceType,
    Intent,
    RecommendedAction,
    Urgency,
)
from app.services.evaluation.metrics import (
    ConfusionCounts,
    MetricsAccumulator,
    entities_match,
)
from app.services.evaluation.runner import run_evaluation


class TestEntityMatching:
    @pytest.mark.parametrize(
        "expected,predicted",
        [("1234ABC", "1234 abc"), (True, "true"), (342.0, 342), ("ayer", "Ayer")],
    )
    def test_equivalent_values_match(self, expected, predicted):
        assert entities_match(expected, predicted)

    @pytest.mark.parametrize(
        "expected,predicted", [("1234ABC", "9999ZZZ"), (True, False), ("ayer", None)]
    )
    def test_different_values_do_not_match(self, expected, predicted):
        assert not entities_match(expected, predicted)

    def test_substring_match_only_applies_to_longer_values(self):
        assert entities_match("ayer por la tarde", "ayer")
        assert not entities_match("no", "nota informativa")


class TestConfusionCounts:
    def test_precision_recall_f1(self):
        counts = ConfusionCounts(true_positive=8, false_positive=2, false_negative=2)

        assert counts.precision == 0.8
        assert counts.recall == 0.8
        assert counts.f1 == pytest.approx(0.8)

    def test_empty_counts_do_not_divide_by_zero(self):
        counts = ConfusionCounts()
        assert (counts.precision, counts.recall, counts.f1) == (0.0, 0.0, 0.0)


class TestMetricsAccumulator:
    @staticmethod
    def expected(**overrides) -> dict:
        return {
            "intent": "CLAIM",
            "urgency": "MEDIUM",
            "insurance_type": "MOTOR",
            "action": "REQUEST_DOCUMENTS",
            "entities": {"vehicle_plate": "1234ABC"},
            "expects_human_review": True,
            **overrides,
        }

    def test_perfect_prediction_scores_one(self):
        accumulator = MetricsAccumulator()
        expected = self.expected()
        accumulator.add(
            expected=expected,
            predicted={
                "intent": "CLAIM",
                "urgency": "MEDIUM",
                "insurance_type": "MOTOR",
                "action": "REQUEST_DOCUMENTS",
                "entities": {"vehicle_plate": "1234 abc"},
                "human_review_required": True,
            },
            latency_ms=100,
            schema_valid=True,
        )
        metrics = accumulator.to_dict()

        assert metrics["intent_accuracy"] == 1.0
        assert metrics["entity_extraction"]["f1"] == 1.0
        assert metrics["human_review_recall_on_risky"] == 1.0

    def test_wrong_intent_is_counted(self):
        accumulator = MetricsAccumulator()
        accumulator.add(
            expected=self.expected(),
            predicted={"intent": "RENEWAL", "human_review_required": True},
            latency_ms=50,
            schema_valid=True,
        )
        assert accumulator.to_dict()["intent_accuracy"] == 0.0

    def test_missed_risky_case_lowers_review_recall(self):
        """The safety metric: a risky case that was not flagged."""
        accumulator = MetricsAccumulator()
        accumulator.add(
            expected=self.expected(),
            predicted={"intent": "CLAIM", "human_review_required": False},
            latency_ms=50,
            schema_valid=True,
        )
        assert accumulator.to_dict()["human_review_recall_on_risky"] == 0.0

    def test_unnecessary_flagging_shows_in_the_false_alarm_rate(self):
        accumulator = MetricsAccumulator()
        accumulator.add(
            expected=self.expected(expects_human_review=False, entities={}),
            predicted={"intent": "CLAIM", "human_review_required": True},
            latency_ms=50,
            schema_valid=True,
        )
        assert accumulator.to_dict()["human_review_false_alarm_rate"] == 1.0

    def test_missing_entity_counts_as_a_false_negative(self):
        accumulator = MetricsAccumulator()
        accumulator.add(
            expected=self.expected(),
            predicted={"intent": "CLAIM", "entities": {}, "human_review_required": True},
            latency_ms=50,
            schema_valid=True,
        )
        entity_metrics = accumulator.to_dict()["entity_extraction"]
        assert entity_metrics["false_negative"] == 1
        assert entity_metrics["recall"] == 0.0

    def test_schema_failure_lowers_the_validation_rate(self):
        accumulator = MetricsAccumulator()
        accumulator.add(
            expected=self.expected(),
            predicted={"intent": "UNKNOWN", "human_review_required": True},
            latency_ms=10,
            schema_valid=False,
        )
        assert accumulator.to_dict()["schema_validation_rate"] == 0.0

    def test_latency_statistics(self):
        accumulator = MetricsAccumulator()
        for latency in (100, 200, 300):
            accumulator.add(
                expected=self.expected(),
                predicted={"intent": "CLAIM", "human_review_required": True},
                latency_ms=latency,
                schema_valid=True,
            )
        metrics = accumulator.to_dict()

        assert metrics["avg_latency_ms"] == 200
        assert metrics["p95_latency_ms"] == 300

    def test_token_usage_accumulates(self):
        accumulator = MetricsAccumulator()
        accumulator.add(
            expected=self.expected(),
            predicted={"intent": "CLAIM", "human_review_required": True},
            latency_ms=10,
            schema_valid=True,
            token_usage={"input_tokens": 900, "output_tokens": 120},
        )
        metrics = accumulator.to_dict()

        assert metrics["total_input_tokens"] == 900
        assert metrics["total_output_tokens"] == 120


class TestEvaluationRunner:
    @staticmethod
    def add_case(session, key: str, text: str, **labels) -> EvaluationCase:
        case = EvaluationCase(
            case_key=key,
            input_text=text,
            expected_intent=labels.get("intent", Intent.CLAIM),
            expected_urgency=labels.get("urgency", Urgency.MEDIUM),
            expected_insurance_type=labels.get("insurance_type", InsuranceType.MOTOR),
            expected_action=labels.get("action", RecommendedAction.REQUEST_DOCUMENTS),
            expected_entities=labels.get("entities", {}),
            expects_human_review=labels.get("expects_human_review", True),
        )
        session.add(case)
        session.flush()
        return case

    def test_run_produces_metrics_and_per_case_results(
        self, session, pipeline, knowledge_base
    ):
        self.add_case(
            session,
            "T-001",
            "Ayer tuve un golpe con el coche, matrícula 1234ABC, sin heridos.",
            entities={"vehicle_plate": "1234ABC"},
        )
        self.add_case(
            session,
            "T-002",
            "Quiero dar de baja mi póliza de hogar al vencimiento.",
            intent=Intent.CANCELLATION,
            insurance_type=InsuranceType.HOME,
            action=RecommendedAction.CANCELLATION_WORKFLOW,
        )

        run = run_evaluation(pipeline, label="unit test run")

        assert run.case_count == 2
        assert len(run.results) == 2
        assert run.metrics["intent_accuracy"] == 1.0
        assert run.metrics["schema_validation_rate"] == 1.0
        assert run.metrics["avg_latency_ms"] >= 0

    def test_run_is_persisted_and_audited(self, session, pipeline, knowledge_base):
        self.add_case(session, "T-010", "Tuve un accidente con el coche.")
        run = run_evaluation(pipeline, label="persisted run")

        assert db.session.get(EvaluationRun, run.id) is not None
        assert (
            db.session.query(AuditLog).filter_by(action=AuditAction.EVALUATION_RUN).count()
            == 1
        )

    def test_run_records_the_model_and_demo_flag(self, session, pipeline, knowledge_base):
        self.add_case(session, "T-020", "Tuve un accidente con el coche.")
        run = run_evaluation(pipeline, label="metadata run")

        assert run.model_name == "demo-rule-engine-v1"
        assert run.demo_mode is True
        assert run.prompt_version == "classification_v1"

    def test_limit_restricts_the_number_of_cases(self, session, pipeline, knowledge_base):
        for index in range(4):
            self.add_case(session, f"T-03{index}", "Tuve un accidente con el coche.")
        assert run_evaluation(pipeline, limit=2).case_count == 2

    def test_empty_dataset_raises_a_clear_error(self, session, pipeline):
        with pytest.raises(ValueError, match="No evaluation cases"):
            run_evaluation(pipeline)

    def test_a_failing_case_does_not_abort_the_run(
        self, session, pipeline, knowledge_base, monkeypatch
    ):
        self.add_case(session, "T-040", "Tuve un accidente con el coche.")
        self.add_case(session, "T-041", "Quiero renovar mi póliza.")

        original = pipeline.run
        calls = {"count": 0}

        def flaky(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("simulated provider outage")
            return original(*args, **kwargs)

        monkeypatch.setattr(pipeline, "run", flaky)
        run = run_evaluation(pipeline, label="resilience run")

        assert run.case_count == 2
        failed = [result for result in run.results if result.error]
        assert len(failed) == 1
        assert run.metrics["schema_validation_rate"] == 0.5


class TestEvaluationApi:
    def test_run_endpoint_returns_metrics(self, client, session, knowledge_base):
        TestEvaluationRunner.add_case(session, "T-100", "Tuve un golpe con el coche.")
        response = client.post("/api/evaluations/run", json={"label": "api run"})

        assert response.status_code == 201
        body = response.get_json()
        assert body["metrics"]["cases"] == 1
        assert body["results"]

    def test_run_with_no_dataset_returns_422(self, client, session):
        assert client.post("/api/evaluations/run", json={}).status_code == 422

    def test_list_runs_includes_the_dataset_size(self, client, session, knowledge_base):
        TestEvaluationRunner.add_case(session, "T-110", "Tuve un golpe con el coche.")
        client.post("/api/evaluations/run", json={})
        body = client.get("/api/evaluations").get_json()

        assert body["dataset_size"] == 1
        assert body["latest"]["metrics"]["cases"] == 1

    def test_missing_run_returns_404(self, client, session):
        assert client.get("/api/evaluations/4242").status_code == 404
