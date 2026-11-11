"""Provider-agnostic LLM interface.

The rest of the application depends on `LLMProvider`, never on a vendor SDK.
Swapping Anthropic for OpenAI (or for the deterministic demo engine) is a
configuration change, and the pipeline, tests and evaluation runner are
unaffected.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    text: str
    model: str
    latency_ms: int
    token_usage: dict[str, int] = field(default_factory=dict)
    # True when the text came from the deterministic mock, not a real model.
    is_demo: bool = False


class LLMError(Exception):
    """Transport/provider failure (timeout, auth, rate limit, bad status)."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class LLMProvider(abc.ABC):
    """Minimal surface: one text-in/text-out call with a system prompt."""

    name: str = "base"

    def __init__(self, *, model: str, temperature: float, max_tokens: int, timeout: int) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    @abc.abstractmethod
    def complete(self, system: str, user: str) -> LLMResponse:
        """Run one completion. Must raise `LLMError` on provider failure."""

    @property
    def is_demo(self) -> bool:
        return False

    def describe(self) -> dict:
        return {
            "provider": self.name,
            "model": self.model,
            "temperature": self.temperature,
            "demo_mode": self.is_demo,
        }


class EmbeddingProvider(abc.ABC):
    """Batch embedding interface used by the RAG ingestion and retriever."""

    name: str = "base"
    dimensions: int = 0
    model: str = "unknown"

    @abc.abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def describe(self) -> dict:
        return {
            "provider": self.name,
            "model": self.model,
            "dimensions": self.dimensions,
        }
