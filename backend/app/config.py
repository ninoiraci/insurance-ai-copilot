"""Application configuration.

All configuration is environment driven so the same image can run locally,
in Docker, or in CI without code changes. Defaults are chosen so that
`python -m flask run` works with zero setup (SQLite + demo AI), which keeps
the project demonstrable even when no infrastructure or API key is present.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent

# .env in the repo root wins, then backend/.env. Neither is required.
for candidate in (REPO_ROOT / ".env", BACKEND_ROOT / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _default_database_url() -> str:
    """SQLite fallback keeps the project runnable without Docker/Postgres.

    Docker Compose always injects a Postgres DATABASE_URL, so the production
    shaped path (pgvector) is the one exercised in the containerised setup.
    """
    return f"sqlite:///{(BACKEND_ROOT / 'instance' / 'copilot.db').as_posix()}"


@dataclass(frozen=True)
class AISettings:
    """Everything the AI layer needs, resolved once at startup."""

    provider: str = "demo"
    api_key: str | None = None
    model: str = "claude-sonnet-4-20250514"
    base_url: str | None = None
    temperature: float = 0.1
    max_tokens: int = 1500
    timeout_seconds: int = 45
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5
    demo_mode_forced: bool = False

    embedding_provider: str = "hashing"
    embedding_model: str = "local-hashing-384"
    embedding_dimensions: int = 384

    confidence_threshold: float = 0.75
    rag_top_k: int = 5
    rag_min_similarity: float = 0.16

    @property
    def demo_mode(self) -> bool:
        """True when no real LLM is reachable and mock outputs are used."""
        return self.provider == "demo"


class Config:
    """Base Flask config object."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or _default_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    JSON_SORT_KEYS = False

    ENV_NAME = os.getenv("FLASK_ENV", "development")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_MESSAGE_BODIES = _bool("LOG_MESSAGE_BODIES", False)

    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]

    KNOWLEDGE_BASE_DIR = Path(
        os.getenv("KNOWLEDGE_BASE_DIR", str(REPO_ROOT / "data" / "knowledge_base"))
    )
    CHUNK_TARGET_CHARS = _int("RAG_CHUNK_TARGET_CHARS", 900)
    CHUNK_OVERLAP_CHARS = _int("RAG_CHUNK_OVERLAP_CHARS", 150)


def build_ai_settings() -> AISettings:
    """Resolve AI settings, falling back to demo mode when unusable.

    Design decision: we never crash when the API key is missing. A missing key
    means "demo mode", which is surfaced explicitly in the API and the UI so a
    reviewer is never misled into thinking mock output came from a real model.
    """
    forced_demo = _bool("AI_DEMO_MODE", False)
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    api_key = (os.getenv("LLM_API_KEY") or "").strip() or None

    if forced_demo or not provider or provider == "demo" or not api_key:
        resolved_provider = "demo"
    elif provider in {"anthropic", "openai"}:
        resolved_provider = provider
    else:
        # Unknown provider string: fail safe rather than fail hard.
        resolved_provider = "demo"

    default_model = {
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4o-mini",
        "demo": "demo-rule-engine-v1",
    }[resolved_provider]

    embedding_provider = (os.getenv("EMBEDDING_PROVIDER") or "hashing").strip().lower()
    if embedding_provider == "openai" and not (
        os.getenv("EMBEDDING_API_KEY") or (api_key if resolved_provider == "openai" else None)
    ):
        embedding_provider = "hashing"

    if embedding_provider == "openai":
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        embedding_dimensions = _int("EMBEDDING_DIMENSIONS", 1536)
    else:
        embedding_provider = "hashing"
        embedding_model = "local-hashing-384"
        embedding_dimensions = _int("EMBEDDING_DIMENSIONS", 384)

    return AISettings(
        provider=resolved_provider,
        api_key=api_key,
        model=os.getenv("LLM_MODEL") or default_model,
        base_url=os.getenv("LLM_BASE_URL") or None,
        temperature=_float("LLM_TEMPERATURE", 0.1),
        max_tokens=_int("LLM_MAX_TOKENS", 1500),
        timeout_seconds=_int("LLM_TIMEOUT_SECONDS", 45),
        max_retries=_int("LLM_MAX_RETRIES", 2),
        retry_backoff_seconds=_float("LLM_RETRY_BACKOFF_SECONDS", 0.5),
        demo_mode_forced=forced_demo,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        confidence_threshold=_float("AI_CONFIDENCE_THRESHOLD", 0.75),
        rag_top_k=_int("RAG_TOP_K", 5),
        rag_min_similarity=_float("RAG_MIN_SIMILARITY", 0.16),
    )
