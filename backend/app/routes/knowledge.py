"""Knowledge base: documents, ingestion trigger and the RAG Playground."""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import AuditAction, KnowledgeDocument
from ..prompts import RAG_ANSWER_PROMPT, get_prompt
from ..schemas.ai_output import AnalysisFailure, GeneratedResponse
from ..schemas.api import IngestRequest, KnowledgeSearchRequest
from ..services.audit import record_audit
from ..services.rag.ingestion import ingest_directory
from ..services.rag.retriever import KnowledgeRetriever
from ..services.rag.vector_store import get_vector_store
from ..utils.errors import NotFoundError
from .helpers import get_ai_stack, get_retriever, parse_body

logger = logging.getLogger(__name__)

bp = Blueprint("knowledge", __name__, url_prefix="/api/knowledge")


@bp.get("/documents")
def list_documents():
    documents = (
        db.session.execute(
            select(KnowledgeDocument)
            # to_dict() reports chunk_count for each document.
            .options(selectinload(KnowledgeDocument.chunks))
            .order_by(KnowledgeDocument.title)
        )
        .scalars()
        .all()
    )
    ai = get_ai_stack()
    return jsonify(
        {
            "items": [document.to_dict() for document in documents],
            "count": len(documents),
            "embedding": ai.embeddings.describe(),
            "vector_backend": get_vector_store().backend,
            "source_directory": str(current_app.config["KNOWLEDGE_BASE_DIR"]),
        }
    )


@bp.get("/documents/<int:document_id>")
def get_document(document_id: int):
    document = db.session.get(KnowledgeDocument, document_id)
    if document is None:
        raise NotFoundError(f"Knowledge document {document_id} does not exist.")
    return jsonify(document.to_dict(include_content=True))


@bp.post("/ingest")
def ingest():
    body = parse_body(IngestRequest)
    ai = get_ai_stack()
    report = ingest_directory(
        current_app.config["KNOWLEDGE_BASE_DIR"],
        ai.embeddings,
        force=body.force,
        target_chars=current_app.config["CHUNK_TARGET_CHARS"],
        overlap_chars=current_app.config["CHUNK_OVERLAP_CHARS"],
    )
    status = 200 if not report.errors else 207  # partial success is real here
    return jsonify({"report": report.to_dict(), "embedding": ai.embeddings.describe()}), status


@bp.post("/search")
def search():
    """RAG Playground: raw retrieval, no generation. Shows scores and sources."""
    body = parse_body(KnowledgeSearchRequest)
    retriever = get_retriever()
    chunks = retriever.search(body.query, top_k=body.top_k)

    record_audit(
        AuditAction.KNOWLEDGE_SEARCHED,
        entity_type="KnowledgeBase",
        metadata={"query_length": len(body.query), "results": len(chunks)},
    )
    db.session.commit()

    return jsonify(
        {
            "query": body.query,
            "results": [chunk.to_dict() for chunk in chunks],
            "count": len(chunks),
            "vector_backend": get_vector_store().backend,
            "embedding": get_ai_stack().embeddings.describe(),
            "min_similarity": retriever.min_similarity,
        }
    )


@bp.post("/answer")
def answer():
    """Grounded answer for an internal operator question. Refuses when unsupported."""
    body = parse_body(KnowledgeSearchRequest)
    ai = get_ai_stack()
    retriever = get_retriever()
    chunks = retriever.search(body.query, top_k=body.top_k)

    prompt = get_prompt(RAG_ANSWER_PROMPT)
    system, user = prompt.render(
        retrieved_knowledge=KnowledgeRetriever.format_for_prompt(chunks),
        question=body.query,
    )

    try:
        response, raw, attempts = ai.client.generate(
            schema=GeneratedResponse, system=system, user=user, label="rag_answer"
        )
        latency_ms, model = raw.latency_ms, raw.model
    except AnalysisFailure as exc:
        logger.error("rag_answer_failed error=%s", exc)
        response = GeneratedResponse(
            response_text=(
                "No dispongo de información suficiente en la base de conocimiento "
                "para responder a esta consulta de forma fiable."
            ),
            used_sources=[],
            grounded=False,
            insufficient_information=True,
        )
        latency_ms, model, attempts = 0, ai.provider.model, exc.attempts

    valid_citations = {chunk.citation for chunk in chunks}
    response.used_sources = [
        source for source in response.used_sources if source in valid_citations
    ]

    return jsonify(
        {
            "query": body.query,
            "answer": response.response_text,
            "grounded": response.grounded and bool(chunks),
            "insufficient_information": response.insufficient_information or not chunks,
            "used_sources": response.used_sources,
            "results": [chunk.to_dict() for chunk in chunks],
            "metadata": {
                "model": model,
                "prompt_version": RAG_ANSWER_PROMPT,
                "latency_ms": latency_ms,
                "attempts": attempts,
                "demo_mode": ai.demo_mode,
            },
        }
    )
