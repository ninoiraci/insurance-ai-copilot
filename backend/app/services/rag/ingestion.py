"""Knowledge-base ingestion: files -> documents -> chunks -> embeddings."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from ...extensions import db
from ...models import AuditAction, KnowledgeChunk, KnowledgeDocument
from ...utils.text import content_fingerprint
from ..ai.base import EmbeddingProvider
from ..audit import record_audit
from .chunking import chunk_document

logger = logging.getLogger(__name__)

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class IngestionReport:
    documents_processed: int = 0
    documents_skipped: int = 0
    chunks_created: int = 0
    embeddings_created: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> dict:
        return {
            "documents_processed": self.documents_processed,
            "documents_skipped": self.documents_skipped,
            "chunks_created": self.chunks_created,
            "embeddings_created": self.embeddings_created,
            "errors": self.errors,
        }


def _parse_frontmatter(raw: str, fallback_title: str) -> tuple[str, str, str]:
    """Return (title, category, body)."""
    match = FRONTMATTER_RE.match(raw)
    title, category = fallback_title, "general"
    body = raw

    if match:
        body = raw[match.end() :]
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key, value = key.strip().lower(), value.strip().strip('"')
            if key == "title":
                title = value
            elif key == "category":
                category = value

    if title == fallback_title:
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if heading:
            title = heading.group(1).strip()

    return title, category, body.strip()


def ingest_directory(
    directory: Path,
    embedder: EmbeddingProvider,
    *,
    force: bool = False,
    target_chars: int = 900,
    overlap_chars: int = 150,
) -> IngestionReport:
    """Ingest every markdown/text file in `directory`.

    Idempotent: a document whose content hash is unchanged is skipped unless
    `force=True`. Re-ingesting a changed document replaces its chunks
    atomically rather than leaving stale vectors behind.
    """
    report = IngestionReport()
    if not directory.exists():
        report.errors.append(f"knowledge base directory not found: {directory}")
        logger.error("knowledge_base_missing path=%s", directory)
        return report

    paths = sorted(
        [path for pattern in ("*.md", "*.txt") for path in directory.glob(pattern)]
    )
    if not paths:
        report.errors.append(f"no .md/.txt documents found in {directory}")

    for path in paths:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            report.errors.append(f"{path.name}: {exc}")
            continue

        title, category, body = _parse_frontmatter(raw, path.stem.replace("_", " ").title())
        fingerprint = content_fingerprint(body)

        document = db.session.query(KnowledgeDocument).filter_by(
            source_filename=path.name
        ).one_or_none()

        if document and document.content_hash == fingerprint and not force:
            report.documents_skipped += 1
            continue

        if document:
            # Replace rather than append: stale chunks would keep being retrieved.
            document.chunks.clear()
            db.session.flush()
        else:
            document = KnowledgeDocument(source_filename=path.name)
            db.session.add(document)

        document.title = title
        document.category = category
        document.content_hash = fingerprint
        document.char_count = len(body)
        document.raw_content = body

        chunks = chunk_document(
            body, title=title, target_chars=target_chars, overlap_chars=overlap_chars
        )
        vectors = embedder.embed([chunk.content for chunk in chunks])

        for chunk, vector in zip(chunks, vectors):
            document.chunks.append(
                KnowledgeChunk(
                    content=chunk.content,
                    chunk_index=chunk.index,
                    section=chunk.section,
                    embedding=vector,
                    embedding_model=embedder.model,
                    chunk_metadata={**chunk.metadata, "category": category},
                )
            )

        report.documents_processed += 1
        report.chunks_created += len(chunks)
        report.embeddings_created += len(vectors)
        logger.info(
            "ingested document=%s chunks=%s category=%s", path.name, len(chunks), category
        )

    db.session.commit()

    record_audit(
        AuditAction.KNOWLEDGE_INGESTED,
        entity_type="KnowledgeBase",
        metadata={
            **report.to_dict(),
            "directory": str(directory),
            "embedding_model": embedder.model,
            "forced": force,
        },
    )
    db.session.commit()
    return report
