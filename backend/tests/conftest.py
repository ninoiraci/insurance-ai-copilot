"""Shared pytest fixtures.

Tests run against a real (temporary) SQLite database and the real service
layer. Only the LLM boundary is mocked - everything else, including the ORM,
the RAG store and the workflow engine, is exercised for real. Mocking the
services would test the mocks rather than the system.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

# Must be set before app.config is imported, since settings are read at import.
os.environ.setdefault("AI_DEMO_MODE", "true")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    Channel,
    Conversation,
    ConversationStatus,
    Customer,
    InsuranceType,
    Message,
    Policy,
    PolicyStatus,
    SenderType,
    utcnow,
)
from app.services.rag.ingestion import ingest_directory  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def app():
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)

    class TestingConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{path}"
        LOG_LEVEL = "WARNING"

    application = create_app(TestingConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()
    os.unlink(path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def session(app):
    """Clean database state between tests."""
    yield db.session
    db.session.rollback()
    for table in reversed(db.metadata.sorted_tables):
        db.session.execute(table.delete())
    db.session.commit()


@pytest.fixture
def pipeline(app):
    return app.extensions["analysis_pipeline"]


@pytest.fixture
def ai_stack(app):
    return app.extensions["ai_stack"]


@pytest.fixture
def customer(session) -> Customer:
    record = Customer(
        full_name="Carlos García Ruiz",
        email="carlos.garcia@example.invalid",
        phone="+34 600 000 001",
        preferred_language="es",
        city="Madrid",
    )
    session.add(record)
    session.flush()
    return record


@pytest.fixture
def motor_policy(session, customer) -> Policy:
    record = Policy(
        customer_id=customer.id,
        policy_number="MOT-90001",
        policy_type=InsuranceType.MOTOR,
        provider="Aseguradora Norte",
        start_date=date.today() - timedelta(days=300),
        expiration_date=date.today() + timedelta(days=65),
        status=PolicyStatus.ACTIVE,
        vehicle_plate="1234ABC",
    )
    session.add(record)
    session.flush()
    return record


def make_conversation(
    session,
    customer: Customer,
    text: str,
    *,
    channel: Channel = Channel.WHATSAPP,
    subject: str = "Test conversation",
) -> Conversation:
    conversation = Conversation(
        customer_id=customer.id,
        channel=channel,
        subject=subject,
        status=ConversationStatus.NEW,
    )
    conversation.messages.append(
        Message(sender_type=SenderType.CUSTOMER, content=text, timestamp=utcnow())
    )
    session.add(conversation)
    session.flush()
    return conversation


@pytest.fixture
def conversation(session, customer, motor_policy) -> Conversation:
    return make_conversation(
        session,
        customer,
        "Hola, ayer tuve un golpe con el coche. No hubo heridos pero tengo el "
        "paragolpes roto. Mi matrícula es 1234ABC. ¿Qué tengo que enviaros?",
    )


@pytest.fixture
def knowledge_base(app, session):
    """Ingest the real knowledge base for tests that need retrieval.

    Function scoped because the `session` fixture truncates every table after
    each test; a session-scoped ingest would silently disappear.
    """
    report = ingest_directory(
        REPO_ROOT / "data" / "knowledge_base",
        app.extensions["ai_stack"].embeddings,
        force=True,
    )
    assert report.chunks_created > 0, "knowledge base failed to ingest"
    return report
