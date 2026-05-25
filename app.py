# -*- coding: utf-8 -*-
"""Compatibility Flask app entrypoint used by tests and scripts."""

from __future__ import annotations

import importlib
from typing import Any, Mapping

from flask import Flask, jsonify


def _build_fallback_app() -> Flask:
    fallback = Flask(__name__)
    fallback.config.setdefault("JWT_SECRET_KEY", "ester-test-local-jwt")

    try:
        from flask_jwt_extended import JWTManager  # type: ignore

        JWTManager(fallback)
    except Exception:
        pass

    @fallback.get("/health")
    def _health() -> Any:
        return jsonify(ok=True, src="app_fallback")

    for module_name in (
        "routes.docs_routes",
        "routes.security_routes",
        "routes.p2p_crdt_routes",
        "routes.p2p_tasks_routes",
        "routes.ops_p2p_diff_routes",
    ):
        try:
            module = importlib.import_module(module_name)
            register = getattr(module, "register", None)
            if callable(register):
                register(fallback)
        except Exception:
            pass

    return fallback


try:
    from run_ester_fixed import flask_app as _flask_app  # type: ignore
except Exception:
    _flask_app = _build_fallback_app()

app: Flask = _flask_app

try:
    from modules.storage.vector_crdt_adapter import VectorCRDTAdapter  # type: ignore

    app.extensions.setdefault("vector_crdt_adapter", VectorCRDTAdapter())
except Exception:
    pass


def create_app(config: Mapping[str, Any] | None = None) -> Flask:
    """Return the project Flask app, optionally applying test config."""
    if config:
        app.config.update(dict(config))
    return app
