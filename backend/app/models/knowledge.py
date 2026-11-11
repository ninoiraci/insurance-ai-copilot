"""RAG storage: source documents and their embedded chunks."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import EmbeddingColumn, JSONColumn, Model, TimestampMixin


class KnowledgeDocument(Model, TimestampMixin):
    __tablename__ = "knowledge_documents"

    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    category: Mapped[str] = mapped_column(sa.String(80), nullable=False, index=True)
    source_filename: Mapped[str] = mapped_column(sa.String(200), unique=True, nullable=False)
    # Detects "has this file changed since the last ingest?" without re-embedding.
    content_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    char_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    raw_content: Mapped[str] = mapped_column(sa.Text, default="", nullable=False)

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="KnowledgeChunk.chunk_index",
    )

    def to_dict(self, *, include_content: bool = False) -> dict:
        payload = {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "source_filename": self.source_filename,
            "chunk_count": len(self.chunks),
            "char_count": self.char_count,
            "content_hash": self.content_hash[:12],
            "created_at": self.created_at.isoformat(),
        }
        if include_content:
            payload["raw_content"] = self.raw_content
            payload["chunks"] = [chunk.to_dict() for chunk in self.chunks]
        return payload


class KnowledgeChunk(Model):
    __tablename__ = "knowledge_chunks"

    document_id: Mapped[int] = mapped_column(
        sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(sa.String(200))
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingColumn())
    embedding_model: Mapped[str | None] = mapped_column(sa.String(80))
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSONColumn, default=dict)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")

    __table_args__ = (
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_document_index"),
    )

    @property
    def citation(self) -> str:
        """Human-readable source label shown in the UI next to a response."""
        section = self.section or f"section {self.chunk_index + 1}"
        return f"{self.document.title}, {section}"

    def to_dict(self, *, include_embedding: bool = False) -> dict:
        payload = {
            "id": self.id,
            "document_id": self.document_id,
            "document_title": self.document.title if self.document else None,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "section": self.section,
            "citation": self.citation if self.document else None,
            "embedding_model": self.embedding_model,
            "metadata": self.chunk_metadata or {},
        }
        if include_embedding:
            payload["embedding"] = self.embedding
        return payload
