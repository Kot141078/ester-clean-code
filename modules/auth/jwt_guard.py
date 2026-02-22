# -*- coding: utf-8 -*-
"""
modules/auth/jwt_guard.py

Yavnaya obertka dlya zaschity routov:
- esli JWT dostupen i initsializirovan -> primenyaet jwt_required()
- esli JWT nedostupen/ne initsializirovan:
    * ESTER_LAB_MODE=1 -> loud warning + propusk (safe-disable)
    * obychnyy rezhim   -> 503 JWT_UNAVAILABLE (fail-closed)
"""
from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable

from flask import current_app, jsonify

try:
    from flask_jwt_extended import jwt_required as _jwt_required  # type: ignore
except Exception:  # pragma: no cover
    _jwt_required = None  # type: ignore


def _truthy(v: Any) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "on", "y")


def _lab_mode_enabled() -> bool:
    return _truthy(os.getenv("ESTER_LAB_MODE", "0"))


def _jwt_runtime_ready() -> bool:
    if _jwt_required is None:
        return False
    try:
        ext = getattr(current_app, "extensions", None) or {}
        return bool(ext.get("flask-jwt-extended"))
    except Exception:
        return False


def _warn(msg: str) -> None:
    try:
        current_app.logger.warning(msg)
    except Exception:
        pass


def require_jwt_or_503() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Dekorator dlya zaschischennykh ruchek.
    """

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        guarded_fn = _jwt_required()(fn) if _jwt_required is not None else None

        @wraps(fn)
        def wrapped(*args: Any, **kwargs: Any):
            if guarded_fn is not None and _jwt_runtime_ready():
                return guarded_fn(*args, **kwargs)

            if _lab_mode_enabled():
                _warn(
                    "JWT guard bypass in LAB mode: flask_jwt_extended unavailable "
                    "or JWTManager not initialized"
                )
                return fn(*args, **kwargs)

            _warn(
                "JWT unavailable for protected route: returning 503 JWT_UNAVAILABLE "
                "(dependency/init missing)"
            )
            return jsonify({"ok": False, "error": "JWT_UNAVAILABLE"}), 503

        return wrapped

    return deco

