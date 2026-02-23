# -*- coding: utf-8 -*-
"""
routes/abslot_routes.py - REST: status/pereklyuchenie A/B-slotov.

Mosty:
- Yavnyy: (Veb ↔ AB) operatorskoe upravlenie pereklyuchatelem A|B.
- Skrytyy #1: (Profile ↔ Prozrachnost) fiksatsiya smen slota.
- Skrytyy #2: (Garage ↔ Eksperimenty) bezopasnye vykaty v B s avtokatbekom.

Zemnoy abzats:
Tot samyy tumbler na paneli: «A» - stabilno; «B» - eksperiment; upal - vernulsya.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("abslot_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.safety.abslot import active_slot as _active  # type: ignore
except Exception:
    _active=None  # type: ignore

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "safety://abslot")
    except Exception:
        pass

@bp.route("/safety/ab/status", methods=["GET"])
def api_status():
    slot = _active() if _active else os.getenv("AB_SLOT","A")
    return jsonify({"ok": True, "slot": slot, "autorollback": (os.getenv("AB_AUTOROLLBACK","true").lower()=="true")})

@bp.route("/safety/ab/switch", methods=["POST"])
def api_switch():
    d=request.get_json(True, True) or {}
    slot=str(d.get("slot","A")).upper()
    if slot not in ("A","B"):
        return jsonify({"ok": False, "error":"invalid_slot"}), 400
    os.environ["AB_SLOT"]=slot
    _passport("abslot_switch", {"slot": slot})
    return jsonify({"ok": True, "slot": slot})
# c=a+b