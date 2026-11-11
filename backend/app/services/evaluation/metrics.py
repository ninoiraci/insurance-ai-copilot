"""Evaluation metrics.

Deliberately simple and explainable. Every number here can be recomputed by
hand from the per-case results, which matters more for a review than a
sophisticated metric nobody can interpret.

Entity scoring note: we score only the keys the dataset labels. A predicted
entity the dataset does not label is *not* counted as a false positive,
because the label set is intentionally partial (we label the entities that
matter for routing, not everything extractable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _normalise(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip().lower().replace(" ", "")


def entities_match(expected: Any, predicted: Any) -> bool:
    """Lenient string comparison: "1234ABC" == "1234 abc"."""
    if expected is None or predicted is None:
        return False
    left, right = _normalise(expected), _normalise(predicted)
    if left == right:
        return True
    # Dates are often returned as a relative phrase ("ayer") when the label is
    # the phrase itself; substring matching keeps that fair without being loose.
    return len(left) > 3 and (left in right or right in left)


@dataclass
class ConfusionCounts:
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)

    def to_dict(self) -> dict:
        return {
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


@dataclass
class MetricsAccumulator:
    total: int = 0
    intent_correct: int = 0
    urgency_correct: int = 0
    insurance_correct: int = 0
    action_correct: int = 0
    schema_valid: int = 0
    latencies: list[int] = field(default_factory=list)
    entities: ConfusionCounts = field(default_factory=ConfusionCounts)

    # Human-review recall on risky cases: of the cases that *should* have been
    # flagged for a human, how many were? This is the safety metric that
    # matters most - a miss here is a wrong answer reaching a customer.
    risky_total: int = 0
    risky_flagged: int = 0
    # And the cost side: cases flagged that did not need it.
    safe_total: int = 0
    safe_flagged: int = 0

    intent_confusion: dict[str, dict[str, int]] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0

    def add(
        self,
        *,
        expected: dict,
        predicted: dict,
        latency_ms: int,
        schema_valid: bool,
        token_usage: dict | None = None,
    ) -> dict:
        self.total += 1
        self.latencies.append(latency_ms)
        if schema_valid:
            self.schema_valid += 1

        if token_usage:
            self.input_tokens += int(token_usage.get("input_tokens", 0) or 0)
            self.output_tokens += int(token_usage.get("output_tokens", 0) or 0)

        correctness = {
            "intent": expected["intent"] == predicted.get("intent"),
            "urgency": expected["urgency"] == predicted.get("urgency"),
            "insurance_type": expected["insurance_type"] == predicted.get("insurance_type"),
            "action": expected["action"] == predicted.get("action"),
        }
        self.intent_correct += correctness["intent"]
        self.urgency_correct += correctness["urgency"]
        self.insurance_correct += correctness["insurance_type"]
        self.action_correct += correctness["action"]

        actual_intent = expected["intent"]
        predicted_intent = predicted.get("intent", "UNKNOWN")
        row = self.intent_confusion.setdefault(actual_intent, {})
        row[predicted_intent] = row.get(predicted_intent, 0) + 1

        entity_hits = 0
        expected_entities = expected.get("entities") or {}
        predicted_entities = predicted.get("entities") or {}
        for key, expected_value in expected_entities.items():
            if key in predicted_entities and entities_match(
                expected_value, predicted_entities[key]
            ):
                self.entities.true_positive += 1
                entity_hits += 1
            elif key in predicted_entities:
                self.entities.false_positive += 1
            else:
                self.entities.false_negative += 1
        correctness["entities_matched"] = entity_hits
        correctness["entities_expected"] = len(expected_entities)

        expects_review = bool(expected.get("expects_human_review"))
        flagged = bool(predicted.get("human_review_required"))
        if expects_review:
            self.risky_total += 1
            self.risky_flagged += flagged
        else:
            self.safe_total += 1
            self.safe_flagged += flagged
        correctness["human_review"] = flagged == expects_review

        return correctness

    def to_dict(self) -> dict:
        def ratio(numerator: int, denominator: int) -> float:
            return round(numerator / denominator, 4) if denominator else 0.0

        sorted_latencies = sorted(self.latencies)
        p95 = (
            sorted_latencies[min(len(sorted_latencies) - 1, int(len(sorted_latencies) * 0.95))]
            if sorted_latencies
            else 0
        )

        return {
            "cases": self.total,
            "intent_accuracy": ratio(self.intent_correct, self.total),
            "urgency_accuracy": ratio(self.urgency_correct, self.total),
            "insurance_type_accuracy": ratio(self.insurance_correct, self.total),
            "action_accuracy": ratio(self.action_correct, self.total),
            "schema_validation_rate": ratio(self.schema_valid, self.total),
            "entity_extraction": self.entities.to_dict(),
            "human_review_recall_on_risky": ratio(self.risky_flagged, self.risky_total),
            "human_review_false_alarm_rate": ratio(self.safe_flagged, self.safe_total),
            "risky_cases": self.risky_total,
            "avg_latency_ms": int(sum(self.latencies) / len(self.latencies))
            if self.latencies
            else 0,
            "p95_latency_ms": p95,
            "total_input_tokens": self.input_tokens,
            "total_output_tokens": self.output_tokens,
            "intent_confusion": self.intent_confusion,
        }
