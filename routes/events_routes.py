# -*- coding: utf-8 -*-
"""
routes/events_routes.py - REST-obertka nad modules.events_bus.

Endpointy:
- POST /events/publish      - publikatsiya sobytiya
- GET  /events/feed         - lenta sobytiy
- GET  /events/last_ts      - posledniy taymstamp

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:
    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn): return fn
        return _wrap

from modules import events_bus  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("events_routes", __name__, url_prefix="/events")

def _headers_meta() -> Dict[str, Any]:
    h = request.headers
    return {
        "trace_id": h.get("X-Trace-Id"),
        "correlation_id": h.get("X-Correlation-Id"),
        "idempotency_key": h.get("Idempotency-Key"),
    }

@bp.post("/publish")
@jwt_required(optional=True)
def publish():
    d: Dict[str, Any] = request.get_json(True, True) or {}
    kind = d.get("kind") or "event"
    payload = d.get("payload") or {}
    meta = _headers_meta()
    try:
        res = events_bus.publish(kind, payload, meta=meta)  # type: ignore[arg-type]
        return jsonify(res)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.get("/feed")
@jwt_required(optional=True)
def feed():
    since = float(request.args.get("since", "0") or 0)
    limit = int(request.args.get("limit", "100") or 100)
    kinds: List[str] = []
    if request.args.get("kinds"):
        kinds = [x for x in request.args.get("kinds", "").split(",") if x]
    return jsonify(events_bus.feed(since=since, limit=limit, kinds=kinds))

@bp.get("/last_ts")
def last_ts():
    return jsonify({"ok": True, "ts": events_bus.last_ts()})

def register(app) -> None:
    if bp.name in getattr(app, "blueprints", {}):
        return
    app.register_blueprint(bp)


def register(app):
    app.register_blueprint(bp)
    return app