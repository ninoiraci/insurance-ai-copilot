"""Retrieval facade used by the pipeline and the RAG Playground."""

from __future__ import annotations

import logging

from ...models import InsuranceType, Intent
from ..ai.base import EmbeddingProvider
from .vector_store import RetrievedChunk, get_vector_store

logger = logging.getLogger(__name__)

# Query expansion terms per intent. Retrieval quality depends heavily on the
# query, and a raw WhatsApp message ("me han dado un golpe") is a poor query
# against a procedure manual. Adding the domain vocabulary of the classified
# intent is a cheap, explainable improvement over embedding the raw text.
INTENT_QUERY_TERMS: dict[Intent, str] = {
    Intent.CLAIM: "procedimiento siniestro documentación obligatoria parte declaración plazos",
    Intent.RENEWAL: "renovación póliza vencimiento aviso previo condiciones",
    Intent.CANCELLATION: "baja cancelación anulación preaviso plazo legal",
    Intent.PAYMENT: "recibo impagado devuelto regularización pago plazo",
    Intent.NEW_QUOTE: "presupuesto contratación nueva póliza documentación alta",
    Intent.DOCUMENT_REQUEST: "documentación requerida documentos necesarios",
    Intent.POLICY_INFORMATION: "coberturas condiciones generales información póliza",
    Intent.POLICY_CHANGE: "modificación suplemento cambio de datos póliza",
    Intent.COMPLAINT: "reclamación escalado defensor del cliente plazos respuesta",
    Intent.CROSS_SELL: "asesoramiento productos comunicación con clientes",
    Intent.GENERAL_SUPPORT: "comunicación con clientes atención",
}

# Which knowledge-base category is authoritative for each intent. Used as a
# small, explicit re-ranking boost - a light hybrid of vector similarity and
# document metadata. It matters most with the local hashing embeddings, where
# pure lexical similarity confuses documents that share common vocabulary
# ("comunicación", "plazo", "documentación") across procedures.
INTENT_CATEGORY: dict[Intent, str] = {
    Intent.CLAIM: "claims",
    Intent.DOCUMENT_REQUEST: "claims",
    Intent.RENEWAL: "renewal",
    Intent.CANCELLATION: "cancellation",
    Intent.PAYMENT: "billing",
    Intent.COMPLAINT: "operations",
}

CATEGORY_BOOST = 0.10

INSURANCE_QUERY_TERMS: dict[InsuranceType, str] = {
    InsuranceType.MOTOR: "automóvil vehículo motor coche",
    InsuranceType.HOME: "hogar vivienda inmueble",
    InsuranceType.HEALTH: "salud asistencia sanitaria",
    InsuranceType.LIFE: "vida beneficiario",
    InsuranceType.TRAVEL: "viaje asistencia en viaje",
    InsuranceType.BUSINESS: "empresa comercio responsabilidad civil",
}


class KnowledgeRetriever:
    def __init__(
        self,
        embedder: EmbeddingProvider,
        *,
        top_k: int = 5,
        min_similarity: float = 0.05,
    ) -> None:
        self.embedder = embedder
        self.top_k = top_k
        self.min_similarity = min_similarity

    def build_query(
        self, message: str, intent: Intent | None = None, insurance: InsuranceType | None = None
    ) -> str:
        """Customer message plus the domain vocabulary of its classification."""
        parts = [message.strip()]
        if intent and intent in INTENT_QUERY_TERMS:
            parts.append(INTENT_QUERY_TERMS[intent])
        if insurance and insurance in INSURANCE_QUERY_TERMS:
            parts.append(INSURANCE_QUERY_TERMS[insurance])
        return " ".join(parts)

    def search(
        self,
        query: str,
        top_k: int | None = None,
        *,
        boost_category: str | None = None,
    ) -> list[RetrievedChunk]:
        """Embed the query and return chunks above the similarity floor.

        Returning nothing is a valid, expected outcome. The response generator
        must then say it lacks information rather than answer ungrounded.
        """
        if not query or not query.strip():
            return []

        limit = top_k or self.top_k
        vector = self.embedder.embed_one(query)
        store = get_vector_store()

        # Over-fetch so the re-rank has something to reorder.
        candidates = store.search(vector, limit * 3 if boost_category else limit)

        if boost_category:
            for chunk in candidates:
                if chunk.category == boost_category:
                    chunk.similarity += CATEGORY_BOOST
            candidates.sort(key=lambda chunk: chunk.similarity, reverse=True)

        results = [
            chunk for chunk in candidates if chunk.similarity >= self.min_similarity
        ][:limit]

        logger.info(
            "rag_search backend=%s candidates=%s kept=%s boost=%s top_similarity=%s",
            store.backend,
            len(candidates),
            len(results),
            boost_category,
            round(candidates[0].similarity, 3) if candidates else None,
        )
        return results

    def retrieve_for_case(
        self, message: str, intent: Intent, insurance: InsuranceType
    ) -> list[RetrievedChunk]:
        return self.search(
            self.build_query(message, intent, insurance),
            boost_category=INTENT_CATEGORY.get(intent),
        )

    @staticmethod
    def format_for_prompt(chunks: list[RetrievedChunk]) -> str:
        """Render chunks with explicit `[Source: ...]` labels the model must cite."""
        if not chunks:
            return (
                "No relevant internal documentation was retrieved for this case. "
                "You must not answer procedural questions from memory."
            )
        return "\n\n".join(
            f"[Source: {chunk.citation}] (similarity {chunk.similarity:.2f})\n{chunk.content}"
            for chunk in chunks
        )
