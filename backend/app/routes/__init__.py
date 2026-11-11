"""Blueprint registration. Route modules stay thin: parse, delegate, serialise."""

from flask import Flask

from . import analyses, audit, conversations, customers, evaluations, knowledge, system

BLUEPRINTS = (
    system.bp,
    customers.bp,
    conversations.bp,
    analyses.bp,
    knowledge.bp,
    evaluations.bp,
    audit.bp,
)


def register_blueprints(app: Flask) -> None:
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)
