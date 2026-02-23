
# -*- coding: utf-8 -*-
from __future__ import annotations
from flask import Blueprint, current_app, jsonify
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("jwt_bootstrap_legacy", __name__)

def _resolve_jwt_secret() -> str:
    secret = (os.environ.get("ESTER_JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or "").strip()
    if secret:
        return secret
    if os.environ.get("ESTER_DEV_MODE", "0").strip() == "1":
        return os.urandom(32).hex()
    return ""

def _apply_defaults(app):
    secret = _resolve_jwt_secret()
    if secret:
        app.config.setdefault("JWT_SECRET_KEY", secret)
    app.config.setdefault("JWT_TOKEN_LOCATION", ["headers", "query_string"])
    app.config.setdefault("JWT_QUERY_STRING_NAME", "jwt")
    app.config.setdefault("JWT_HEADER_NAME", "Authorization")
    app.config.setdefault("JWT_HEADER_TYPE", "Bearer")

@bp.route("/_jwt/legacy/status", methods=["GET"])
def jwt_status():
    app = current_app._get_current_object()
    _apply_defaults(app)
    info = {
        "ok": True,
        "ab": os.environ.get("ESTER_JWT_BOOTSTRAP_AB", "A"),
        "JWT_TOKEN_LOCATION": app.config.get("JWT_TOKEN_LOCATION"),
        "JWT_HEADER_NAME": app.config.get("JWT_HEADER_NAME"),
        "JWT_HEADER_TYPE": app.config.get("JWT_HEADER_TYPE"),
        "has_secret": bool(app.config.get("JWT_SECRET_KEY")),
    }
    return jsonify(info)
