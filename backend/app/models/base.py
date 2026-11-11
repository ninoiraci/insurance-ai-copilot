"""Shared column types and mixins.

Two portability decisions live here, both deliberate:

1. `JSONColumn` renders as JSONB on PostgreSQL and JSON elsewhere, so the
   production database gets indexable binary JSON without breaking SQLite.
2. `EmbeddingColumn` renders as a real pgvector `vector(n)` column on
   PostgreSQL and as JSON on SQLite. This lets vector similarity run inside
   the database in the Docker/Postgres setup while keeping the project
   runnable with zero infrastructure for a quick review.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db

# Fixed at table-creation time: switching embedding provider means a migration
# plus a re-ingest. Documented in docs/ARCHITECTURE.md.
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "384"))

JSONColumn = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


class EmbeddingColumn(sa.types.TypeDecorator):
    """Vector column that degrades to JSON on databases without pgvector."""

    impl = sa.JSON
    cache_ok = True

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):  # noqa: D102 - SQLAlchemy hook
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector

                return dialect.type_descriptor(Vector(self.dimensions))
            except ImportError:  # pragma: no cover - pgvector is a hard dep in Docker
                return dialect.type_descriptor(postgresql.JSONB())
        return dialect.type_descriptor(sa.JSON())

    def process_bind_param(self, value, dialect):
        """Hand a plain list to the underlying type.

        Both impls serialise it themselves - pgvector renders `vector` literals,
        and SQLAlchemy's JSON type encodes the list. Returning `json.dumps(...)`
        here instead made the JSON type encode an already-encoded string, so
        every embedding was stored double-encoded.
        """
        if value is None:
            return None
        return [float(component) for component in value]

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        # `str` covers rows written before the double-encoding fix.
        if isinstance(value, str):
            return json.loads(value)
        return list(value)


def utcnow() -> datetime:
    """Timezone-aware UTC now; stored naive to stay portable across engines."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enum_column(enum_cls, **kwargs):
    """Store enums as VARCHAR with a CHECK constraint.

    Native PostgreSQL enum types make migrations painful (ALTER TYPE cannot run
    in a transaction with other DDL), and the taxonomy here is expected to grow.
    """
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=40,
        values_callable=lambda cls: [member.value for member in cls],
        **kwargs,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime, default=utcnow, nullable=False, index=True
    )


class Model(db.Model):
    """Abstract base giving every table an integer surrogate primary key."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} id={self.id}>"
