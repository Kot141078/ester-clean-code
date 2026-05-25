# -*- coding: utf-8 -*-
"""Compatibility Flask app entrypoint used by tests and scripts."""

from __future__ import annotations

import importlib
from typing import Any, Mapping

from flask import Flask, jsonify


def _install_routes_endpoint(target: Flask) -> None:
    """Expose a small route inventory for test and diagnostic clients."""
    if any(rule.rule == "/routes" for rule in target.url_map.iter_rules()):
        return

    @target.get("/routes")
    def _routes_inventory() -> Any:
        routes = []
        fallback_mode = bool(target.config.get("ESTER_FALLBACK_APP"))
        for rule in target.url_map.iter_rules():
            if rule.endpoint == "static":
                continue
            path = str(rule.rule)
            if fallback_mode and path.startswith(("/ops", "/providers/select", "/ingest")):
                continue
            methods = sorted(method for method in rule.methods if method not in {"HEAD", "OPTIONS"})
            routes.append({"rule": path, "endpoint": rule.endpoint, "methods": methods})
        routes.sort(key=lambda item: item["rule"])
        return jsonify({"ok": True, "count": len(routes), "routes": routes})


def _build_fallback_app() -> Flask:
    fallback = Flask(__name__)
    fallback.config["ESTER_FALLBACK_APP"] = True
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
        "routes.ingest_crdt_adapter_routes",
        "routes.probe_routes",
        "routes.proactive_routes",
        "routes.ready_routes",
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
_install_routes_endpoint(app)

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
