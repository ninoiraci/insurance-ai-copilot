"""Embedding providers.

Two implementations:

* `OpenAIEmbeddingProvider` - real semantic embeddings, used when an embedding
  API key is configured.
* `HashingEmbeddingProvider` - a deterministic, offline, hashed bag-of-ngrams
  vectoriser. It is **lexical, not semantic**: it matches on shared words and
  character n-grams, so "coche" will not retrieve "vehículo" unless both appear.
  It exists so the RAG pipeline genuinely runs end-to-end with no API key.
  This limitation is stated in the UI and in docs/AI_PIPELINE.md.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import unicodedata

from .base import EmbeddingProvider, LLMError

logger = logging.getLogger(__name__)

# Spanish + English function words carry no retrieval signal.
STOPWORDS = frozenset(
    """
    el la los las un una unos unas de del al a en y o u que se su sus por para
    con sin sobre entre es son ser esta este estos estas lo le les mi mis tu tus
    como mas más pero si no ni ya hay he ha han fue era muy tambien también
    the of and to in is are for with on at be by an it this that as from or
    """.split()
)

TOKEN_RE = re.compile(r"[a-z0-9áéíóúüñ]+")


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in TOKEN_RE.findall(_fold(text))
        if len(token) > 1 and token not in STOPWORDS
    ]


class HashingEmbeddingProvider(EmbeddingProvider):
    """Hashed n-gram vectoriser with sublinear term frequency and L2 norm."""

    name = "hashing"

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions
        self.model = f"local-hashing-{dimensions}"

    def _features(self, text: str) -> dict[str, float]:
        tokens = tokenize(text)
        features: dict[str, float] = {}

        for token in tokens:
            features[f"w:{token}"] = features.get(f"w:{token}", 0.0) + 1.0
            # Character 4-grams give partial credit for typos and inflections
            # ("matricula" vs "matriculas"), which matters for WhatsApp text.
            if len(token) > 4:
                for start in range(len(token) - 3):
                    gram = token[start : start + 4]
                    features[f"c:{gram}"] = features.get(f"c:{gram}", 0.0) + 0.4

        for first, second in zip(tokens, tokens[1:]):
            key = f"b:{first}_{second}"
            features[key] = features.get(key, 0.0) + 0.8

        return features

    def _vectorize(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for feature, count in self._features(text).items():
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0  # signed hashing reduces collisions
            vector[index] += sign * (1.0 + math.log(count))

        norm = math.sqrt(sum(component * component for component in vector))
        if norm == 0.0:
            return vector
        return [component / norm for component in vector]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vectorize(text or "") for text in texts]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai"

    def __init__(self, *, api_key: str, model: str, dimensions: int, timeout: int = 30) -> None:
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise LLMError("openai SDK is not installed", retryable=False) from exc
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout)
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self._client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions,
            )
        except Exception as exc:
            raise LLMError(f"embedding call failed: {exc}") from exc
        return [item.embedding for item in response.data]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Plain cosine similarity, used by the portable (SQLite) vector store."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
