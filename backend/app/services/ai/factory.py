"""Builds the AI stack from configuration, once per application.

Fail-safe by design: if a real provider cannot be constructed (missing SDK,
bad key), we log loudly and fall back to DEMO MODE rather than taking the whole
application down. A broken AI provider should degrade the product, not break it.
"""

from __future__ import annotations

import logging
import os

from ...config import AISettings
from .base import EmbeddingProvider, LLMProvider
from .demo_provider import DemoProvider
from .embeddings import HashingEmbeddingProvider, OpenAIEmbeddingProvider
from .structured import StructuredLLMClient

logger = logging.getLogger(__name__)


def build_llm_provider(settings: AISettings) -> LLMProvider:
    if settings.provider == "demo":
        reason = "AI_DEMO_MODE=true" if settings.demo_mode_forced else "no LLM_API_KEY configured"
        logger.warning("AI running in DEMO MODE (%s) - outputs are mock, not model output", reason)
        return DemoProvider()

    common = {
        "model": settings.model,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "timeout": settings.timeout_seconds,
    }
    try:
        if settings.provider == "anthropic":
            from .providers import AnthropicProvider

            provider: LLMProvider = AnthropicProvider(
                api_key=settings.api_key or "", base_url=settings.base_url, **common
            )
        else:
            from .providers import OpenAIProvider

            provider = OpenAIProvider(
                api_key=settings.api_key or "", base_url=settings.base_url, **common
            )
    except Exception:
        logger.exception(
            "failed to initialise provider '%s' - falling back to DEMO MODE", settings.provider
        )
        return DemoProvider()

    logger.info("AI provider=%s model=%s", provider.name, provider.model)
    return provider


def build_embedding_provider(settings: AISettings) -> EmbeddingProvider:
    if settings.embedding_provider == "openai":
        api_key = os.getenv("EMBEDDING_API_KEY") or settings.api_key
        try:
            return OpenAIEmbeddingProvider(
                api_key=api_key or "",
                model=settings.embedding_model,
                dimensions=settings.embedding_dimensions,
            )
        except Exception:
            logger.exception("failed to initialise OpenAI embeddings - using local hashing")

    return HashingEmbeddingProvider(dimensions=settings.embedding_dimensions)


class AIStack:
    """Everything AI-related, resolved once and attached to the Flask app."""

    def __init__(self, settings: AISettings) -> None:
        self.settings = settings
        self.provider = build_llm_provider(settings)
        self.client = StructuredLLMClient(
            self.provider,
            max_retries=settings.max_retries,
            # The demo provider never fails in transport; waiting would
            # only slow the offline demo and the test suite down.
            backoff_seconds=0.0 if self.provider.is_demo else settings.retry_backoff_seconds,
        )
        self.embeddings = build_embedding_provider(settings)

    @property
    def demo_mode(self) -> bool:
        return self.provider.is_demo

    def describe(self) -> dict:
        return {
            "demo_mode": self.demo_mode,
            "demo_mode_forced": self.settings.demo_mode_forced,
            "llm": self.provider.describe(),
            "embeddings": self.embeddings.describe(),
            "confidence_threshold": self.settings.confidence_threshold,
            "rag_top_k": self.settings.rag_top_k,
            "max_retries": self.settings.max_retries,
        }
