"""Flask application factory.

The AI stack and the analysis pipeline are built **once** at startup and stored
in `app.extensions`. Constructing a provider per request would waste
connections and make demo-mode logging noisy; building it once also means a
misconfiguration is visible in the startup logs rather than on first use.
"""

from __future__ import annotations

import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS

from .cli import register_cli
from .config import Config, build_ai_settings
from .extensions import db, migrate
from .routes import register_blueprints
from .services.ai.factory import AIStack
from .services.workflows.pipeline import AnalysisPipeline
from .utils.errors import register_error_handlers
from .utils.request_context import configure_logging, register_request_hooks

logger = logging.getLogger(__name__)

__version__ = "1.0.0"


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object or Config)

    configure_logging(app.config["LOG_LEVEL"])

    # SQLite needs its directory to exist before the engine connects.
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if uri.startswith("sqlite:///") and ":memory:" not in uri:
        os.makedirs(os.path.dirname(uri.replace("sqlite:///", "")), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(os.path.dirname(__file__), "..", "migrations"))
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        expose_headers=["X-Request-ID"],
    )

    ai_settings = build_ai_settings()
    ai_stack = AIStack(ai_settings)
    app.extensions["ai_stack"] = ai_stack
    app.extensions["analysis_pipeline"] = AnalysisPipeline(
        ai_stack, ai_settings, log_message_bodies=app.config["LOG_MESSAGE_BODIES"]
    )

    register_request_hooks(app)
    register_error_handlers(app)
    register_blueprints(app)
    register_cli(app)

    @app.get("/")
    def index():
        return jsonify(
            {
                "name": "Insurance Conversation Intelligence - AI Case Copilot",
                "version": __version__,
                "api_root": "/api",
                "demo_mode": ai_stack.demo_mode,
                "notice": "All data served by this API is synthetic.",
            }
        )

    logger.info(
        "application ready env=%s db=%s demo_mode=%s model=%s",
        app.config["ENV_NAME"],
        uri.split("@")[-1],  # never log credentials from a Postgres URL
        ai_stack.demo_mode,
        ai_stack.provider.model,
    )
    return app
