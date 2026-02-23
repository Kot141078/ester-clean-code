# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, render_template
try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:
    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn):
            return fn
        return _wrap

try:
    from p2p.discovery import peers
except Exception:
    def peers() -> list[Any]:  # type: ignore
        return []

from p2p.sync_client import state_level
from routes.p2p_crdt_routes import CRDT  # drop-in globalnyy CRDT
try:
    from scheduler.sync_job import sync_once
except Exception:
    def sync_once() -> Dict[str, Any]:  # type: ignore
        return {"ok": False, "note": "sync scheduler unavailable"}
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ops_p2p = Blueprint("ops_p2p", __name__, template_folder="../templates")


def _safe_peers() -> list[Any]:
    try:
        data = peers()
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def _safe_local_state() -> Dict[str, Any] | None:
    if not os.getenv("DEBUG_LOCAL_STATE"):
        return None
    try:
        st = state_level("http://localhost:5000", level=0)
        return st if isinstance(st, dict) and st.get("ok") else None
    except Exception as e:
        return {"ok": False, "state": "not_ready", "note": str(e)}


def _safe_visible_count() -> int:
    try:
        visible_items = getattr(CRDT, "visible_items", None)
        if callable(visible_items):
            items = visible_items()
            if isinstance(items, list):
                return len(items)
        visible_count = getattr(CRDT, "visible_count", None)
        if callable(visible_count):
            value = visible_count()
            if isinstance(value, int):
                return value
    except Exception:
        pass
    return 0


@bp_ops_p2p.get("/ops/p2p")
@jwt_required(optional=True)
def ops_p2p_index():
    peer = str(getattr(CRDT, "peer_id", "") or "peer-not-initialized")
    clock_raw = getattr(CRDT, "clock", 0)
    try:
        clock = int(clock_raw)
    except Exception:
        clock = 0

    summary = {
        "peer": peer,
        "clock": clock,
        "visible_count": _safe_visible_count(),
        "peers": _safe_peers(),
        "local_state": _safe_local_state(),
        "status": "p2p not initialized" if peer == "peer-not-initialized" else "ok",
    }
    return render_template("ops_p2p.html", summary=summary)


@bp_ops_p2p.post("/ops/p2p/sync")
@jwt_required()
def ops_p2p_sync():
    res = sync_once()
    return jsonify({"ok": True, "result": res})


def register(app):
    app.register_blueprint(bp_ops_p2p)
    return app
