"""Regression tests for defects found during the code review.

Each test names the defect it locks down. They are grouped here rather than
scattered so the review trail stays readable.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models import AIAnalysis, KnowledgeChunk, KnowledgeDocument, Task, TaskStatus
from app.schemas.ai_output import MessageAnalysis
from app.services.ai.base import LLMError
from app.services.ai.structured import StructuredLLMClient
from app.services.rag.vector_store import (
    PgVectorStore,
    PortableVectorStore,
    get_vector_store,
)
from app.utils.request_context import sanitize_request_id
from app.services.workflows.business_rules import apply_business_rules
from tests.conftest import make_conversation
from tests.test_llm_reliability import VALID_JSON, ScriptedProvider


class TestVectorStoreSelection:
    """`db.session.bind` is always None under Flask-SQLAlchemy, so the old
    dialect check silently disabled pgvector on PostgreSQL."""

    def test_sqlite_uses_the_portable_store(self, app):
        assert isinstance(get_vector_store(), PortableVectorStore)

    def test_postgresql_selects_pgvector(self, app):
        with patch.object(
            type(db), "engine", new_callable=lambda: property(
                lambda self: SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
            )
        ):
            assert isinstance(get_vector_store(), PgVectorStore)

    def test_unavailable_engine_degrades_instead_of_raising(self, app):
        def boom(self):
            raise RuntimeError("no application context")

        with patch.object(type(db), "engine", new_callable=lambda: property(boom)):
            assert isinstance(get_vector_store(), PortableVectorStore)


class TestEmbeddingStorage:
    """Embeddings were JSON-encoded by hand and then encoded again by the JSON
    column, so every vector was stored as a string containing JSON."""

    def test_embedding_round_trips_as_a_list(self, session):
        document = KnowledgeDocument(
            title="T", category="c", source_filename="t.md", content_hash="h"
        )
        document.chunks.append(
            KnowledgeChunk(content="x", chunk_index=0, embedding=[0.5, -0.25, 0.125])
        )
        session.add(document)
        session.commit()
        db.session.expunge_all()

        stored = db.session.query(KnowledgeChunk).one()
        assert isinstance(stored.embedding, list)
        assert stored.embedding == [0.5, -0.25, 0.125]

    def test_raw_column_is_a_json_array_not_a_quoted_string(self, session):
        document = KnowledgeDocument(
            title="T", category="c", source_filename="t2.md", content_hash="h"
        )
        document.chunks.append(KnowledgeChunk(content="x", chunk_index=0, embedding=[1.0]))
        session.add(document)
        session.commit()

        raw = db.session.execute(
            db.text("SELECT embedding FROM knowledge_chunks LIMIT 1")
        ).scalar()
        assert raw.startswith("["), f"expected a JSON array, got {raw[:20]!r}"


class TestRequestIdSanitisation:
    """The inbound X-Request-ID was stored unvalidated in a VARCHAR(40) column
    and echoed back, so a long or hostile value broke inserts on PostgreSQL."""

    @pytest.mark.parametrize(
        "value", ["abc123", "trace-me-123", "a.b_c-1", "A" * 40]
    )
    def test_accepts_safe_ids(self, value):
        assert sanitize_request_id(value) == value

    @pytest.mark.parametrize(
        "value",
        [
            "A" * 41,
            "has space",
            "line\nbreak",
            "semi;colon",
            "<script>",
            "",
            None,
        ],
    )
    def test_rejects_unsafe_ids(self, value):
        assert sanitize_request_id(value) is None

    def test_endpoint_does_not_echo_an_oversized_id(self, client):
        response = client.get("/api/health", headers={"X-Request-ID": "B" * 300})
        echoed = response.headers["X-Request-ID"]

        assert echoed != "B" * 300
        assert len(echoed) <= 40

    def test_persisted_request_id_fits_the_column(self, client, conversation, knowledge_base):
        from app.models import AuditLog

        client.post(
            f"/api/conversations/{conversation.id}/analyze",
            json={},
            headers={"X-Request-ID": "C" * 200},
        )
        for entry in db.session.query(AuditLog).all():
            assert entry.request_id is None or len(entry.request_id) <= 40


class TestTaskAnalysisLinkage:
    """Approving a draft used to advance every open AI task on the
    conversation, including ones belonging to a different analysis."""

    def test_task_records_the_analysis_that_created_it(
        self, client, conversation, knowledge_base
    ):
        analysis_id = client.post(
            f"/api/conversations/{conversation.id}/analyze", json={}
        ).get_json()["analysis"]["id"]

        task = db.session.query(Task).filter_by(conversation_id=conversation.id).one()
        assert task.ai_analysis_id == analysis_id

    def test_approving_one_analysis_leaves_the_other_task_untouched(
        self, client, conversation, knowledge_base
    ):
        first = client.post(
            f"/api/conversations/{conversation.id}/analyze", json={}
        ).get_json()["analysis"]["id"]
        second = client.post(
            f"/api/conversations/{conversation.id}/analyze", json={"force": True}
        ).get_json()["analysis"]["id"]

        client.post(f"/api/analyses/{second}/review", json={"action": "APPROVE"})

        tasks = {
            task.ai_analysis_id: task.status
            for task in db.session.query(Task).filter_by(conversation_id=conversation.id)
        }
        assert tasks[second] is TaskStatus.IN_PROGRESS
        assert tasks[first] is TaskStatus.OPEN, "an unrelated task was advanced"


class TestRetryBackoff:
    """Retrying a rate-limited provider with no delay just burns the budget."""

    def test_retryable_error_waits_before_retrying(self):
        provider = ScriptedProvider([LLMError("rate limited", retryable=True), VALID_JSON])
        client = StructuredLLMClient(provider, max_retries=2, backoff_seconds=0.05)

        started = time.perf_counter()
        client.generate(schema=MessageAnalysis, system="s", user="u", label="t")
        elapsed = time.perf_counter() - started

        assert elapsed >= 0.02, "no backoff was applied between provider retries"

    def test_schema_failure_retries_immediately(self):
        """A malformed reply is deterministic; waiting would not help."""
        provider = ScriptedProvider(["not json", VALID_JSON])
        client = StructuredLLMClient(provider, max_retries=2, backoff_seconds=5.0)

        started = time.perf_counter()
        client.generate(schema=MessageAnalysis, system="s", user="u", label="t")

        assert time.perf_counter() - started < 1.0

    def test_demo_provider_never_sleeps(self, ai_stack):
        assert ai_stack.client.backoff_seconds == 0.0


class TestAnalysisObjectIsNotMutated:
    """The pipeline used to overwrite `analysis.urgency` with the rule engine's
    value, destroying the model's own answer."""

    def test_storage_dict_does_not_claim_urgency(self):
        analysis = MessageAnalysis.model_validate(
            {
                "intent": "CLAIM",
                "insurance_type": "MOTOR",
                "urgency": "LOW",
                "confidence": 0.9,
                "summary": "s",
            }
        )
        assert "urgency" not in analysis.to_storage_dict()

    def test_rules_do_not_modify_the_model_output(self):
        analysis = MessageAnalysis.model_validate(
            {
                "intent": "CLAIM",
                "insurance_type": "MOTOR",
                "urgency": "LOW",
                "confidence": 0.9,
                "summary": "s",
                "extracted_entities": {"injuries": True},
            }
        )
        rules = apply_business_rules(analysis, None, raw_message="hay un herido")

        assert rules.urgency.value == "CRITICAL"
        assert analysis.urgency.value == "LOW", "the model's answer was overwritten"

    def test_persisted_urgency_comes_from_the_rules(
        self, client, session, customer, knowledge_base
    ):
        conversation = make_conversation(
            session,
            customer,
            "Hemos tenido un accidente y se han llevado a mi mujer en ambulancia.",
        )
        body = client.post(
            f"/api/conversations/{conversation.id}/analyze", json={}
        ).get_json()["analysis"]

        assert body["urgency"] == "CRITICAL"
        stored = db.session.get(AIAnalysis, body["id"])
        assert stored.urgency.value == "CRITICAL"
        # The override records what the model originally said.
        assert stored.rule_overrides[0]["from"] == "MEDIUM"
        assert stored.rule_overrides[0]["to"] == "CRITICAL"
