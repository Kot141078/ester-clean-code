# -*- coding: utf-8 -*-
"""
UI + API route for internal JWT minting.

Endpoints:
  GET  /auth/ui
  POST /auth/ui/mint
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import jwt
from flask import Blueprint, jsonify, render_template, request

try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:  # pragma: no cover
    def jwt_required(*_args, **_kwargs):  # type: ignore
        def _wrap(fn):
            return fn

        return _wrap


auth_ui_bp = Blueprint("auth_ui", __name__)


def _jwt_secret() -> str:
    sec = str(os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET_KEY") or "").strip()
    if not sec:
        raise RuntimeError("JWT_SECRET / JWT_SECRET_KEY is not set")
    return sec


def _roles_for_name(name: str) -> List[str]:
    admins = [s.strip().lower() for s in str(os.getenv("ADMIN_USERNAMES") or "owner,admin").split(",") if s.strip()]
    if str(name or "").strip().lower() in admins:
        return ["admin", "user"]
    return ["user"]


def _issue_internal_jwt(subject: str, roles: List[str]) -> str:
    secret = _jwt_secret()
    ttl_days = int(os.getenv("JWT_TTL_DAYS", "30"))
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "roles": roles,
        "iss": "ester",
        "aud": "ester",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=ttl_days)).timestamp()),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token if isinstance(token, str) else token.decode("utf-8")


def _append_identity_memory(username: str, roles: List[str]) -> None:
    """Best-effort audit memory line for issued token."""
    try:
        from routes.telegram_feed import _build_mm  # type: ignore

        mm = _build_mm()
        mm.structured.add_record(  # type: ignore[attr-defined]
            text=f"[AUTH] user={username}; roles={','.join(roles)}",
            tags=["auth", f"user:{username}"],
            weight=0.3,
        )
    except Exception:
        pass


@auth_ui_bp.get("/auth/ui")
@jwt_required(optional=True)
def auth_ui_page():
    return render_template("auth_ui.html")


@auth_ui_bp.post("/auth/ui/mint")
@jwt_required(optional=True)
def auth_ui_mint():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    username = str(data.get("username") or data.get("subject") or "").strip() or "user"
    role_hint = str(data.get("role") or "").strip().lower()
    try:
        roles = ["admin", "user"] if role_hint == "admin" else _roles_for_name(username)
        token = _issue_internal_jwt(subject=username, roles=roles)
        _append_identity_memory(username, roles)
        return jsonify({"ok": True, "sub": username, "roles": roles, "token": token, "jwt": token})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


def register_auth_ui_routes(app) -> None:
    app.register_blueprint(auth_ui_bp)


def register(app):  # pragma: no cover
    app.register_blueprint(auth_ui_bp)


def init_app(app):  # pragma: no cover
    app.register_blueprint(auth_ui_bp)


__all__ = ["auth_ui_bp", "register_auth_ui_routes", "register", "init_app"]
