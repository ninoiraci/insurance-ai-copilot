"""Concrete LLM providers: Anthropic and OpenAI.

Both are thin adapters. All prompt construction, JSON parsing, validation,
retries and business logic live outside this file so that provider code stays
trivially reviewable and swappable.
"""

from __future__ import annotations

import logging
import time

from .base import LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, *, api_key: str, base_url: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise LLMError("anthropic SDK is not installed", retryable=False) from exc
        client_kwargs = {"api_key": api_key, "timeout": self.timeout}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = anthropic.Anthropic(**client_kwargs)
        self._sdk = anthropic

    # Anthropic has no JSON mode. Prefilling the assistant turn with "{" is the
    # supported way to force a JSON object: the model continues from that
    # token, so it cannot open with prose or a markdown fence. The prefill is
    # not echoed back, so it is prepended to the response before parsing.
    _JSON_PREFILL = "{"

    def complete(self, system: str, user: str) -> LLMResponse:
        started = time.perf_counter()
        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system,
                messages=[
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": self._JSON_PREFILL},
                ],
            )
        except self._sdk.APIStatusError as exc:
            # 4xx other than 429 will not succeed on retry.
            retryable = exc.status_code in {408, 429} or exc.status_code >= 500
            raise LLMError(f"anthropic status {exc.status_code}", retryable=retryable) from exc
        except self._sdk.APIConnectionError as exc:
            raise LLMError(f"anthropic connection error: {exc}") from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise LLMError(f"anthropic call failed: {exc}") from exc

        continuation = "".join(
            block.text for block in message.content if block.type == "text"
        )
        return LLMResponse(
            text=self._JSON_PREFILL + continuation,
            model=self.model,
            latency_ms=int((time.perf_counter() - started) * 1000),
            token_usage={
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
        )


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, *, api_key: str, base_url: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise LLMError("openai SDK is not installed", retryable=False) from exc
        client_kwargs = {"api_key": api_key, "timeout": self.timeout}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = openai.OpenAI(**client_kwargs)
        self._sdk = openai

    def complete(self, system: str, user: str) -> LLMResponse:
        started = time.perf_counter()
        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                # Guarantees syntactically valid JSON; semantic validation is
                # still done by Pydantic downstream.
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except self._sdk.APIStatusError as exc:
            retryable = exc.status_code in {408, 429} or exc.status_code >= 500
            raise LLMError(f"openai status {exc.status_code}", retryable=retryable) from exc
        except self._sdk.APIConnectionError as exc:
            raise LLMError(f"openai connection error: {exc}") from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise LLMError(f"openai call failed: {exc}") from exc

        usage = completion.usage
        return LLMResponse(
            text=completion.choices[0].message.content or "",
            model=self.model,
            latency_ms=int((time.perf_counter() - started) * 1000),
            token_usage={
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
            },
        )
