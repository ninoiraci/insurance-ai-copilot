"""Flask CLI commands.

Kept out of the app factory so `create_app()` stays a short, readable list of
wiring steps. Every setup path a human runs - schema, demo data, knowledge
ingestion, evaluation - is a command here, so nothing lives only in a README.
"""

from __future__ import annotations

import logging

import click
from flask import Flask
from flask_migrate import upgrade
from sqlalchemy import text

from .extensions import db
from .services.ai.factory import AIStack
from .services.rag.ingestion import ingest_directory

logger = logging.getLogger(__name__)


def register_cli(app: Flask) -> None:
    @app.cli.command("seed")
    @click.option("--reset", is_flag=True, help="Drop and recreate the schema first.")
    def seed_command(reset: bool) -> None:
        """Load synthetic customers, policies, conversations and eval cases."""
        from scripts.seed_demo_data import seed_all

        if reset:
            reset_schema()
            click.echo("Schema reset.")
        _echo(seed_all())
        click.echo("Seed complete.")

    @app.cli.command("ingest-knowledge")
    @click.option("--force", is_flag=True, help="Re-embed even if content is unchanged.")
    def ingest_command(force: bool) -> None:
        """Ingest data/knowledge_base into the vector store."""
        _echo(_ingest(app, force=force).to_dict())

    @app.cli.command("evaluate")
    @click.option("--label", default="cli run", help="Label stored with the run.")
    @click.option("--limit", type=int, default=None, help="Only run the first N cases.")
    def evaluate_command(label: str, limit: int | None) -> None:
        """Run the evaluation suite and print the metrics."""
        from .services.evaluation.runner import run_evaluation

        run = run_evaluation(app.extensions["analysis_pipeline"], label=label, limit=limit)
        click.echo(f"\nEvaluation run #{run.id} ({run.case_count} cases, {run.duration_ms} ms)")
        click.echo(f"  model: {run.model_name} (demo_mode={run.demo_mode})")
        for key in (
            "intent_accuracy",
            "urgency_accuracy",
            "insurance_type_accuracy",
            "action_accuracy",
            "schema_validation_rate",
            "human_review_recall_on_risky",
            "avg_latency_ms",
        ):
            click.echo(f"  {key}: {run.metrics[key]}")
        entity = run.metrics["entity_extraction"]
        click.echo(
            f"  entity_f1: {entity['f1']} "
            f"(precision {entity['precision']}, recall {entity['recall']})"
        )

    @app.cli.command("bootstrap")
    @click.option("--reset", is_flag=True, help="Drop and recreate the schema first.")
    def bootstrap_command(reset: bool) -> None:
        """One command: migrate, seed data, ingest knowledge.

        Uses Alembic rather than `create_all()`, so local setup and the Docker
        entrypoint take the same schema path. Two paths would eventually
        diverge and only one of them would be tested.
        """
        from scripts.seed_demo_data import seed_all

        if reset:
            reset_schema(migrate_after=False)
        enable_pgvector()
        upgrade()

        click.echo("Bootstrap complete:")
        _echo({**seed_all(), **_ingest(app, force=True).to_dict()})


def _ingest(app: Flask, *, force: bool):
    stack: AIStack = app.extensions["ai_stack"]
    return ingest_directory(
        app.config["KNOWLEDGE_BASE_DIR"],
        stack.embeddings,
        force=force,
        target_chars=app.config["CHUNK_TARGET_CHARS"],
        overlap_chars=app.config["CHUNK_OVERLAP_CHARS"],
    )


def _echo(summary: dict) -> None:
    for key, value in summary.items():
        click.echo(f"  {key}: {value}")


def enable_pgvector() -> None:
    """Create the pgvector extension when running on PostgreSQL."""
    if db.engine.dialect.name != "postgresql":
        return
    with db.engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.commit()
    logger.info("pgvector extension ensured")


def reset_schema(*, migrate_after: bool = True) -> None:
    """Drop every table, including Alembic's version marker.

    Dropping application tables while leaving `alembic_version` behind would
    make the next `db upgrade` a no-op against an empty database - a
    particularly confusing way to fail.
    """
    db.drop_all()
    with db.engine.connect() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        connection.commit()

    if migrate_after:
        enable_pgvector()
        upgrade()
