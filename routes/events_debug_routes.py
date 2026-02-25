# -*- coding: utf-8 -*-
"""routes/events_debug_routes - prostaya otladka shiny sobytiy.

MOSTY:
- Yavnyy: (Razrabotchik/operatsii ↔ Shina) /debug/events - lenta; /debug/events/publish - hand push.
- Skrytyy #1: (Planirovschik ↔ Vizualizatsiya) udobno videt sobytiya ot run_due().
- Skrytyy #2: (Diagnostika ↔ Istoriya) bystryy obzor poslednego uchastka bez chteniya faylov.

ZEMNOY ABZATs:
This is “okoshko v zhurnal”: odnim zaprosom vidno, chto napublikovali zadachi i chto realno prishlo.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Local final line protection
try:
    a  # type: ignore[name-defined]
    b  # type: ignore[name-defined]
except NameError:
    a = ""  # type: ignore[assignment]
    b = ""  # type: ignore[assignment]

bp = Blueprint("events_debug_routes", __name__, url_prefix="/debug/events")

try:
    from modules import events_bus as _bus  # type: ignore
except Exception:
    _bus = None  # type: ignore


@bp.get("")
def list_events():
    limit = request.args.get("limit", default=50, type=int)
    if _bus is None:
        return jsonify({"ok": True, "items": [], "count": 0, "note": "events_bus not available"})
    return jsonify(_bus.feed(limit=limit))


@bp.post("/publish")
def publish():
    body: Dict[str, Any] = request.get_json(silent=True) or {}
    kind = str(body.get("kind") or "debug")
    payload = body.get("payload")
    if _bus is None:
        return jsonify({"ok": False, "error": "events_bus not available"}), 500
    return jsonify(_bus.publish(kind, payload))


def register(app):
    app.register_blueprint(bp)


# finalnaya stroka
c = a + b