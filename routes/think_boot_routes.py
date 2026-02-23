# -*- coding: utf-8 -*-
"""
routes/think_boot_routes.py - REST dlya upravleniya tsiklom myshleniya Ester.

Marshruty:
  POST /think_boot/config       {"impl":"A|B","max_workers":2,"nice_ms":25}
  POST /think_boot/start        -
  POST /think_boot/stop         -
  GET  /think_boot/status       -
  POST /think_boot/task         {"kind":"consolidate_memory" | "note" | "build_index", ...}

Mosty:
- Yavnyy (Veb ↔ Mysl): knopki upravleniya i ochered zadach dostupny iz HTTP/UI.
- Skrytyy #1 (Mysl ↔ Memory): zadachi otrazhayutsya v events.jsonl (faylovaya shina).
- Skrytyy #2 (Operatsii ↔ Bezopasnost): safe_mode i avtostop pri anomaliyakh, bez vneshnikh zavisimostey.

Zemnoy abzats:
Eto «knopka start/stop dvigatelya» i «lotok zadach». Vse lokalno - ne trebuet klyuchey/klaudov.
Rabotaet na Windows: potok-demon, myagkie zaderzhki, bez tyazhelykh zavisimostey.

# c=a+b
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.thinking.loop_basic import configure as _cfg, start as _start, stop as _stop, status as _status, enqueue as _enqueue  # type: ignore
except Exception:
    _cfg = _start = _stop = _status = _enqueue = None  # type: ignore

bp = Blueprint("think_boot_routes", __name__)

def register(app):
    app.register_blueprint(bp)

@bp.post("/think_boot/config")
def think_config():
    if _cfg is None:
        return jsonify({"ok": False, "error": "thinking engine unavailable"}), 500
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    return jsonify(_cfg(d))

@bp.post("/think_boot/start")
def think_start():
    if _start is None:
        return jsonify({"ok": False, "error": "thinking engine unavailable"}), 500
    return jsonify(_start())

@bp.post("/think_boot/stop")
def think_stop():
    if _stop is None:
        return jsonify({"ok": False, "error": "thinking engine unavailable"}), 500
    return jsonify(_stop())

@bp.get("/think_boot/status")
def think_status():
    if _status is None:
        return jsonify({"ok": False, "error": "thinking engine unavailable"}), 500
    return jsonify(_status())

@bp.post("/think_boot/task")
def think_task():
    if _enqueue is None:
        return jsonify({"ok": False, "error": "thinking engine unavailable"}), 500
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    if "kind" not in d:
        return jsonify({"ok": False, "error": "kind is required"}), 400
    return jsonify(_enqueue(d))
# c=a+b