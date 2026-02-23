
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, current_app, jsonify, request
import os, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    import jwt as pyjwt  # PyJWT
except Exception as e:  # pragma: no cover
    pyjwt = None

bp = Blueprint("auto_jwt_routes", __name__)

def _get_secret() -> str:
    app = current_app._get_current_object()
    secret = app.config.get("JWT_SECRET_KEY") or os.environ.get("ESTER_JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
    secret = str(secret).strip()
    if not secret:
        raise RuntimeError("JWT secret missing. Set ESTER_JWT_SECRET or JWT_SECRET_KEY.")
    return secret

def _mint(subject: str = "user", role: str = "ADMIN", ttl_seconds: int = 12*60*60) -> str:
    assert pyjwt is not None, "PyJWT is required"
    now = int(time.time())
    payload: Dict[str, Any] = {
        "sub": subject or "user",
        "role": role or "USER",
        "iat": now,
        "exp": now + int(ttl_seconds),
    }
    token = pyjwt.encode(payload, _get_secret(), algorithm="HS256")
    return token if isinstance(token, str) else token.decode("utf-8")

@bp.route("/auth/auto/api/issue", methods=["POST"])
def auth_auto_api_issue():
    try:
        data = request.get_json(silent=True) or {}
        subject = data.get("user") or data.get("subject") or "user"
        role = data.get("role") or "ADMIN"
        ttl = int(data.get("ttl") or 12*60*60)
        token = _mint(subject=subject, role=role, ttl_seconds=ttl)
        return jsonify(ok=True, jwt=token)
    except Exception as e:
        return jsonify(ok=False, error=str(e), jwt=""), 500

@bp.route("/auth/ui/mint", methods=["POST"])
def auth_ui_mint():
    try:
        data = request.get_json(silent=True) or {}
        subject = data.get("subject") or data.get("user") or "user"
        role = data.get("role") or "ADMIN"
        ttl = int(data.get("ttl") or 12*60*60)
        token = _mint(subject=subject, role=role, ttl_seconds=ttl)
        return jsonify(ok=True, token=str(token))
    except Exception as e:
        return jsonify(ok=False, error=str(e), token=""), 500
