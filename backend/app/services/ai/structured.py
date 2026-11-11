"""Structured-output client: prompt -> JSON -> validated Pydantic model.

This is where LLM unreliability is contained. Everything that can go wrong with
a model call is handled in one place:

* prose wrapped around the JSON            -> tolerant extraction
* markdown fences                          -> stripped
* syntactically invalid JSON               -> retry with the parser error
* valid JSON that violates the schema      -> retry with the validation error
* provider timeout / 5xx / rate limit      -> retry if retryable
* still failing after N attempts           -> raise `AnalysisFailure`

The caller decides what a final failure means; the pipeline turns it into a
safe fallback analysis that demands human review.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from ...schemas.ai_output import AnalysisFailure
from .base import LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json_object(text: str) -> str:
    """Pull the first balanced JSON object out of a model response."""
    if not text or not text.strip():
        raise ValueError("empty model response")

    fenced = _FENCE_RE.search(text)
    candidate = fenced.group(1).strip() if fenced else text.strip()

    start = candidate.find("{")
    if start == -1:
        raise ValueError("no JSON object found in model response")

    # Brace matching that ignores braces inside strings.
    depth, in_string, escaped = 0, False, False
    for index in range(start, len(candidate)):
        char = candidate[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return candidate[start : index + 1]
    raise ValueError("unterminated JSON object in model response")


class StructuredLLMClient:
    """Wraps an `LLMProvider` with JSON parsing, schema validation and retries."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
    ) -> None:
        self.provider = provider
        self.max_retries = max(0, max_retries)
        # Backoff applies only to *transport* failures. A schema failure is
        # deterministic - the model will not start producing valid JSON because
        # we waited - so those retry immediately.
        self.backoff_seconds = max(0.0, backoff_seconds)

    @property
    def model_name(self) -> str:
        return self.provider.model

    @property
    def is_demo(self) -> bool:
        return self.provider.is_demo

    def generate(
        self,
        *,
        schema: type[ModelT],
        system: str,
        user: str,
        label: str = "llm_call",
    ) -> tuple[ModelT, LLMResponse, int]:
        """Return (validated model, raw response, attempts used)."""
        correction = ""
        last_error: str = "unknown error"
        last_raw: str | None = None

        for attempt in range(1, self.max_retries + 2):
            try:
                response = self.provider.complete(system, user + correction)
            except LLMError as exc:
                last_error = str(exc)
                logger.warning(
                    "%s provider_error attempt=%s retryable=%s error=%s",
                    label,
                    attempt,
                    exc.retryable,
                    exc,
                )
                if not exc.retryable:
                    raise AnalysisFailure(
                        f"{label}: provider error ({exc})", attempts=attempt
                    ) from exc
                # Immediately re-hitting a rate-limited or overloaded provider
                # just burns the retry budget. Exponential backoff with jitter.
                if self.backoff_seconds:
                    delay = self.backoff_seconds * (2 ** (attempt - 1))
                    delay *= 0.5 + random.random()  # jitter: avoid lockstep retries
                    logger.info("%s backing off %.2fs before retry", label, delay)
                    time.sleep(delay)
                continue

            last_raw = response.text
            try:
                payload = json.loads(extract_json_object(response.text))
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = f"JSON parse error: {exc}"
                logger.warning("%s parse_failure attempt=%s error=%s", label, attempt, exc)
                correction = self._correction(last_error)
                continue

            try:
                validated = schema.model_validate(payload)
            except ValidationError as exc:
                last_error = _summarise_validation_error(exc)
                logger.warning(
                    "%s schema_failure attempt=%s errors=%s", label, attempt, last_error
                )
                correction = self._correction(last_error)
                continue

            logger.info(
                "%s ok model=%s attempts=%s latency_ms=%s",
                label,
                response.model,
                attempt,
                response.latency_ms,
            )
            return validated, response, attempt

        raise AnalysisFailure(
            f"{label}: no valid output after {self.max_retries + 1} attempts ({last_error})",
            attempts=self.max_retries + 1,
            raw=last_raw,
        )

    @staticmethod
    def _correction(error: str) -> str:
        """Append the concrete failure so the retry is informed, not blind."""
        return (
            "\n\n---\nYour previous reply was rejected by the schema validator.\n"
            f"Error: {error}\n"
            "Return ONLY a single valid JSON object that satisfies the schema. "
            "No prose, no markdown fences."
        )


def _summarise_validation_error(exc: ValidationError, limit: int = 4) -> str:
    parts = [
        f"{'.'.join(str(item) for item in error['loc']) or 'root'}: {error['msg']}"
        for error in exc.errors()[:limit]
    ]
    return "; ".join(parts)
