# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, jsonify, request

from modules.dreams.store import DreamStore
from modules.security.admin_guard import require_admin
from modules.runtime.status_iter18 import (
    run_dream_once,
    runtime_status,
    start_background_if_enabled,
)

try:
    from flask_jwt_extended import jwt_required as _jwt_required  # type: ignore

    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn):
            wrapped = _jwt_required(*args, **kwargs)(fn)

            def _safe(*a, **k):
                try:
                    return wrapped(*a, **k)
                except Exception:
                    return fn(*a, **k)

            _safe.__name__ = getattr(fn, "__name__", "jwt_optional_safe")
            return _safe

        return _wrap
except Exception:
    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn):
            return fn

        return _wrap


bp_dreams = Blueprint("dreams_routes", __name__)


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "on", "y"}:
        return True
    if s in {"0", "false", "no", "off", "n"}:
        return False
    return bool(default)


def _admin_guard():
    ok, reason = require_admin(request)
    if ok:
        return None
    return jsonify({"ok": False, "error": "forbidden", "reason": reason}), 403


@bp_dreams.get("/debug/runtime/status")
def debug_runtime_status():
    denied = _admin_guard()
    if denied:
        return denied
    return jsonify(runtime_status())


@bp_dreams.get("/debug/dreams/status")
def debug_dreams_status():
    denied = _admin_guard()
    if denied:
        return denied
    st = runtime_status()
    return jsonify(
        {
            "ok": True,
            "memory_ready": st.get("memory_ready"),
            "degraded_memory_mode": st.get("degraded_memory_mode"),
            "dreams": st.get("dreams"),
            "background": st.get("background"),
        }
    )


@bp_dreams.post("/debug/dreams/run_once")
def debug_dreams_run_once():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    dry = _as_bool(request.args.get("dry"), _as_bool(body.get("dry"), False))
    budgets = body.get("budgets") if isinstance(body.get("budgets"), dict) else None
    rep = run_dream_once(dry=dry, budgets=budgets)
    code = 200 if rep.get("ok") else 503
    return jsonify(rep), code


@bp_dreams.post("/dreams/run")
@jwt_required(optional=True)
def dreams_run():
    body = request.get_json(silent=True) or {}
    dry = _as_bool(request.args.get("dry"), _as_bool(body.get("dry"), False))
    budgets = body.get("budgets") if isinstance(body.get("budgets"), dict) else None
    rep = run_dream_once(dry=dry, budgets=budgets)
    code = 200 if rep.get("ok") else 503
    return jsonify(rep), code


@bp_dreams.get("/dreams/last_report")
@jwt_required(optional=True)
def dreams_last_report():
    store = DreamStore()
    tail = store.tail(limit=1)
    if tail:
        return jsonify(tail[0])
    return jsonify({"ok": False, "error": "no_report"}), 404


def register(app):
    if bp_dreams.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(bp_dreams)
    start_background_if_enabled()
    return app
