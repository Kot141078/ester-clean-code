# -*- coding: utf-8 -*-
"""
routes/timekeeper_routes.py - REST dlya khranitelya vremeni.

Mosty:
- Yavnyy: (Veb ↔ Vremya) statusy i otmetki/zametki.
- Skrytyy #1: (Kripto ↔ TTL) prigodno dlya diagnostiki problem s priglasheniyami/podpisyami.
- Skrytyy #2: (Operatsii ↔ Nablyudaemost) legko integriruetsya v konsol.

Zemnoy abzats:
Proverili chasy - spokoynee zhivem.

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_time = Blueprint("timekeeper", __name__)

try:
    from modules.time.keeper import status as _status, mark as _mark, note as _note  # type: ignore
except Exception:
    _status = _mark = _note = None  # type: ignore

def register(app):
    app.register_blueprint(bp_time)

@bp_time.route("/timekeeper/status", methods=["GET"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"timekeeper unavailable"}), 500
    return jsonify(_status())

@bp_time.route("/timekeeper/mark", methods=["POST"])
def api_mark():
    if _mark is None: return jsonify({"ok": False, "error":"timekeeper unavailable"}), 500
    return jsonify(_mark())

@bp_time.route("/timekeeper/note", methods=["POST"])
def api_note():
    if _note is None: return jsonify({"ok": False, "error":"timekeeper unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(_note(str(d.get("source","manual")), int(d.get("offset_ms",0))))
# c=a+b