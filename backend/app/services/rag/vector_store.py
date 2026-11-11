"""Vector similarity search with two interchangeable backends.

`PgVectorStore`   - cosine distance computed inside PostgreSQL via pgvector's
                    `<=>` operator. This is the path Docker Compose runs and
                    the one that scales.
`PortableVectorStore` - loads chunk vectors and ranks them in Python. Used on
                    SQLite so the project runs with zero infrastructure. Fine
                    for a few hundred chunks, obviously not for production.

The selection is automatic, based on the database dialect, so no caller has to
know which one is active.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass

from sqlalchemy import select, text

from ...extensions import db
from ...models import KnowledgeChunk, KnowledgeDocument
from ..ai.embeddings import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_title: str
    section: str
    content: str
    similarity: float
    citation: str
    category: str = "general"

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "section": self.section,
            "content": self.content,
            "similarity": round(self.similarity, 4),
            "citation": self.citation,
            "category": self.category,
        }


class VectorStore(abc.ABC):
    backend: str = "abstract"

    @abc.abstractmethod
    def search(self, query_vector: list[float], top_k: int) -> list[RetrievedChunk]:
        ...


class PortableVectorStore(VectorStore):
    """In-Python cosine ranking. Correct, simple, and O(n) per query."""

    backend = "portable-python"

    def search(self, query_vector: list[float], top_k: int) -> list[RetrievedChunk]:
        rows = db.session.execute(
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeChunk.embedding.is_not(None))
        ).all()

        scored: list[RetrievedChunk] = []
        for chunk, document in rows:
            section = chunk.section or f"section {chunk.chunk_index + 1}"
            scored.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    document_title=document.title,
                    section=section,
                    content=chunk.content,
                    similarity=cosine_similarity(query_vector, chunk.embedding or []),
                    citation=f"{document.title}, {section}",
                    category=document.category,
                )
            )

        scored.sort(key=lambda item: item.similarity, reverse=True)
        return scored[:top_k]


class PgVectorStore(VectorStore):
    """Cosine distance in the database. `1 - (a <=> b)` gives similarity."""

    backend = "pgvector"

    def search(self, query_vector: list[float], top_k: int) -> list[RetrievedChunk]:
        statement = text(
            """
            SELECT c.id                AS chunk_id,
                   d.id                AS document_id,
                   d.title             AS document_title,
                   d.category          AS category,
                   c.section           AS section,
                   c.chunk_index       AS chunk_index,
                   c.content           AS content,
                   1 - (c.embedding <=> CAST(:query AS vector)) AS similarity
            FROM knowledge_chunks c
            JOIN knowledge_documents d ON d.id = c.document_id
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(:query AS vector)
            LIMIT :top_k
            """
        )
        rows = db.session.execute(
            statement,
            {"query": "[" + ",".join(str(value) for value in query_vector) + "]", "top_k": top_k},
        ).mappings()

        results: list[RetrievedChunk] = []
        for row in rows:
            section = row["section"] or f"section {row['chunk_index'] + 1}"
            results.append(
                RetrievedChunk(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    document_title=row["document_title"],
                    section=section,
                    content=row["content"],
                    similarity=float(row["similarity"]),
                    citation=f"{row['document_title']}, {section}",
                    category=row["category"],
                )
            )
        return results


def get_vector_store() -> VectorStore:
    """Pick the backend that matches the connected database.

    Uses `db.engine`, not `db.session.bind`: Flask-SQLAlchemy constructs its
    sessions without an explicit bind (it resolves engines per-mapper), so
    `db.session.bind` is always None and this function silently returned the
    portable store even on PostgreSQL.
    """
    try:
        dialect = db.engine.dialect.name
    except Exception:  # pragma: no cover - only outside an app context
        logger.warning("could not determine database dialect; using portable store")
        return PortableVectorStore()

    if dialect == "postgresql":
        return PgVectorStore()
    return PortableVectorStore()
