# -*- coding: utf-8 -*-
"""Compatibility Flask app entrypoint used by tests and scripts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import json
import os
import time
from typing import Any, Mapping

from flask import Flask, Response, jsonify, render_template, request


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _portal_jwt_secrets() -> list[bytes]:
    secrets: list[bytes] = []
    seen: set[str] = set()
    for name in ("JWT_SECRET", "JWT_SECRET_KEY", "ESTER_JWT_SECRET"):
        value = str(os.getenv(name, "") or "").strip()
        if value and value not in seen:
            seen.add(value)
            secrets.append(value.encode("utf-8"))
    return secrets


def _roles_from_claims(claims: Mapping[str, Any]) -> set[str]:
    roles: set[str] = set()
    raw_roles = claims.get("roles")
    if isinstance(raw_roles, str):
        roles.add(raw_roles.strip().lower())
    elif isinstance(raw_roles, (list, tuple, set)):
        roles.update(str(role).strip().lower() for role in raw_roles if str(role).strip())
    raw_role = claims.get("role")
    if isinstance(raw_role, str) and raw_role.strip():
        roles.add(raw_role.strip().lower())
    raw_scope = claims.get("scope")
    if isinstance(raw_scope, str):
        roles.update(part.strip().lower() for part in raw_scope.split() if part.strip())
    return roles


def _verified_admin_portal_claims(token: str) -> Mapping[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        if str(header.get("alg", "")).upper() != "HS256":
            return None
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        signature = _b64url_decode(parts[2])
    except Exception:
        return None

    secrets = _portal_jwt_secrets()
    if not secrets:
        return None
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    if not any(
        hmac.compare_digest(hmac.new(secret, signing_input, hashlib.sha256).digest(), signature) for secret in secrets
    ):
        return None

    exp = payload.get("exp")
    if exp is not None:
        try:
            if float(exp) < time.time():
                return None
        except (TypeError, ValueError):
            return None

    if "admin" not in _roles_from_claims(payload):
        return None
    return payload


def _admin_portal_claims_from_request() -> Mapping[str, Any] | None:
    auth = str(request.headers.get("Authorization", "") or "")
    if not auth.lower().startswith("bearer "):
        return None
    return _verified_admin_portal_claims(auth.split(" ", 1)[1].strip())


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

    @fallback.get("/portal")
    @fallback.get("/portal/")
    def _portal() -> Any:
        if _admin_portal_claims_from_request() is None:
            return jsonify(ok=False, error="admin_jwt_required"), 401
        try:
            return render_template("portal.html")
        except Exception:
            html = (
                "<!doctype html><meta charset='utf-8'>"
                "<title>Ester Portal</title>"
                "<main id='portal'><h1>Ester Portal</h1></main>"
            )
            return Response(html, mimetype="text/html; charset=utf-8")

    for module_name in (
        "routes.docs_routes",
        "routes.admin_reports_routes",
        "routes.ingest_crdt_adapter_routes",
        "routes.probe_routes",
        "routes.proactive_routes",
        "routes.ready_routes",
        "routes.security_routes",
        "routes.ops_backup_routes",
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
