# -*- coding: utf-8 -*-
"""routes/hold_routes.py - REST-obvyazka uzhe podklyuchennogo middleware “Bolshogo stopa”.

Mosty:
- Yavnyy: (Veb ↔ Chelovek) somewhere convenient imet pryamye ruchki otdelno ot midlvari.
- Skrytyy #1: (Audit ↔ Prozrachnost) soglasovano s zhurnalom hold_chain.jsonl.
- Skrytyy #2: (Politika ↔ Ostorozhnost) popadaet pod cautious-pravila (high).

Zemnoy abzats:
Stop i start - bystro i yavno.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_hold_routes = Blueprint("hold_routes", __name__)

try:
    from middleware.hold_fire import status as _status, set_hold as _set  # type: ignore
except Exception:
    _status = _set = None  # type: ignore

def register(app):
    app.register_blueprint(bp_hold_routes)

@bp_hold_routes.route("/ops/hold/status", methods=["GET"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"hold unavailable"}), 500
    return _status()

@bp_hold_routes.route("/ops/hold/set", methods=["POST"])
def api_set():
    if _set is None: return jsonify({"ok": False, "error":"hold unavailable"}), 500
    return _set()
# c=a+b