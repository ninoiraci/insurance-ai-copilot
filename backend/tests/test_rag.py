"""Chunking, ingestion, retrieval and the empty-result path."""

from __future__ import annotations

from app.extensions import db
from app.models import InsuranceType, Intent, KnowledgeChunk, KnowledgeDocument
from app.services.ai.embeddings import HashingEmbeddingProvider, cosine_similarity
from app.services.rag.chunking import chunk_document
from app.services.rag.retriever import KnowledgeRetriever
from app.services.rag.vector_store import PortableVectorStore, get_vector_store

SAMPLE = """# Procedimiento de Prueba

Texto introductorio del documento.

## 1. Primera sección

Contenido de la primera sección con detalle suficiente.

## 2. Segunda sección

Contenido de la segunda sección.
"""


class TestChunking:
    def test_splits_on_section_headings(self):
        chunks = chunk_document(SAMPLE, title="Procedimiento de Prueba")
        sections = [chunk.section for chunk in chunks]

        assert "1. Primera sección" in sections
        assert "2. Segunda sección" in sections

    def test_h1_matching_the_title_is_not_cited_as_itself(self):
        chunks = chunk_document(SAMPLE, title="Procedimiento de Prueba")
        assert chunks[0].section == "introducción"

    def test_chunk_content_is_prefixed_with_its_heading(self):
        chunks = chunk_document(SAMPLE, title="Procedimiento de Prueba")
        assert chunks[1].content.startswith("1. Primera sección")

    def test_indices_are_sequential(self):
        chunks = chunk_document(SAMPLE, title="Doc")
        assert [chunk.index for chunk in chunks] == list(range(len(chunks)))

    def test_oversized_section_is_split(self):
        long_body = "# Doc\n\n## Sección\n\n" + ("Frase de relleno. " * 400)
        chunks = chunk_document(long_body, title="Doc", target_chars=400, overlap_chars=50)
        assert len(chunks) > 2

    def test_document_without_headings_still_produces_a_chunk(self):
        chunks = chunk_document("Solo texto plano sin encabezados.", title="Doc")
        assert len(chunks) == 1


class TestEmbeddings:
    def test_deterministic(self):
        provider = HashingEmbeddingProvider(dimensions=128)
        assert provider.embed_one("siniestro de coche") == provider.embed_one(
            "siniestro de coche"
        )

    def test_dimensions_are_respected(self):
        assert len(HashingEmbeddingProvider(dimensions=64).embed_one("hola")) == 64

    def test_related_text_scores_higher_than_unrelated(self):
        provider = HashingEmbeddingProvider()
        query = provider.embed_one("documentación necesaria para un siniestro de coche")
        related = provider.embed_one("documentación obligatoria del siniestro de automóvil")
        unrelated = provider.embed_one("horario de apertura de la oficina en agosto")

        assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)

    def test_accents_do_not_break_matching(self):
        provider = HashingEmbeddingProvider()
        assert (
            cosine_similarity(
                provider.embed_one("matrícula"), provider.embed_one("matricula")
            )
            > 0.5
        )

    def test_empty_text_yields_a_zero_vector(self):
        assert not any(HashingEmbeddingProvider().embed_one(""))


class TestRetrieval:
    def test_ingestion_creates_documents_and_chunks(self, knowledge_base):
        assert knowledge_base.documents_processed == 10
        assert knowledge_base.chunks_created > 30
        assert knowledge_base.errors == []
        assert db.session.query(KnowledgeDocument).count() == 10

    def test_every_chunk_has_an_embedding(self, knowledge_base):
        chunks = db.session.query(KnowledgeChunk).all()
        assert chunks and all(chunk.embedding for chunk in chunks)

    def test_reingest_is_idempotent(self, app, knowledge_base):
        from app.services.rag.ingestion import ingest_directory

        before = db.session.query(KnowledgeChunk).count()
        report = ingest_directory(
            app.config["KNOWLEDGE_BASE_DIR"], app.extensions["ai_stack"].embeddings
        )

        assert report.documents_skipped == 10
        assert report.documents_processed == 0
        assert db.session.query(KnowledgeChunk).count() == before

    def test_claim_query_retrieves_the_claims_procedure(self, app, knowledge_base):
        retriever = app.extensions["analysis_pipeline"].retriever
        chunks = retriever.retrieve_for_case(
            "Tuve un golpe con el coche, ¿qué documentación necesito enviar?",
            Intent.CLAIM,
            InsuranceType.MOTOR,
        )
        titles = {chunk.document_title for chunk in chunks}

        assert chunks
        assert any("Siniestros" in title or "Documentación" in title for title in titles)

    def test_cancellation_query_retrieves_the_cancellation_procedure(
        self, app, knowledge_base
    ):
        retriever = app.extensions["analysis_pipeline"].retriever
        chunks = retriever.retrieve_for_case(
            "Quiero dar de baja mi póliza de hogar", Intent.CANCELLATION, InsuranceType.HOME
        )
        assert "Procedimiento de Baja y Cancelación" in {
            chunk.document_title for chunk in chunks
        }

    def test_results_are_ordered_by_similarity(self, app, knowledge_base):
        retriever = app.extensions["analysis_pipeline"].retriever
        chunks = retriever.search("documentación obligatoria del siniestro")
        similarities = [chunk.similarity for chunk in chunks]
        assert similarities == sorted(similarities, reverse=True)

    def test_every_chunk_exposes_a_citation(self, app, knowledge_base):
        retriever = app.extensions["analysis_pipeline"].retriever
        chunks = retriever.search("plazo de comunicación del siniestro")
        assert all("," in chunk.citation for chunk in chunks)

    def test_unrelated_query_returns_nothing(self, app, knowledge_base):
        """No result is a valid outcome, not an error."""
        retriever = app.extensions["analysis_pipeline"].retriever
        assert retriever.search("zxqwv plurbo frimbulator wobbledygook") == []

    def test_empty_query_returns_nothing(self, app, knowledge_base):
        assert app.extensions["analysis_pipeline"].retriever.search("   ") == []

    def test_search_on_an_empty_knowledge_base_returns_nothing(self, app, session):
        retriever = app.extensions["analysis_pipeline"].retriever
        assert retriever.search("documentación de siniestro") == []

    def test_empty_results_produce_a_refusal_instruction_for_the_prompt(self):
        rendered = KnowledgeRetriever.format_for_prompt([])
        assert "No relevant internal documentation" in rendered
        assert "must not answer" in rendered

    def test_prompt_block_labels_every_source(self, app, knowledge_base):
        retriever = app.extensions["analysis_pipeline"].retriever
        chunks = retriever.search("documentación obligatoria del siniestro")
        rendered = KnowledgeRetriever.format_for_prompt(chunks)
        assert rendered.count("[Source:") == len(chunks)

    def test_sqlite_selects_the_portable_backend(self, app):
        assert isinstance(get_vector_store(), PortableVectorStore)
        assert get_vector_store().backend == "portable-python"
