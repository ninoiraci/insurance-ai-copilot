"""Flask extension singletons, kept separate to avoid circular imports."""

from __future__ import annotations

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Explicit declarative base so models can be imported without an app."""


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
