# -*- coding: utf-8 -*-
"""
routes/spread_guard_routes.py — REST dlya proverki politiki samorasprostraneniya.

Mosty:
- Yavnyy: (Beb v†" Politika) peredacha spiska tseley, otvet allow/deny.
- Skrytyy #1: (Goverie v†" Ostorozhnost) v svyazke s priglasheniyami daet bezopasnyy kontur rasprostraneniya.
- Skrytyy #2: (Planer v†" Avtonomiya) udobno zvat iz /self/autonomy/plan pered realnoy otpravkoy.

Zemnoy abzats:
Bystryy test: «tuda mozhno?». Esli net — menyaem marshrut.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_spread = Blueprint("spread_guard", __name__)

try:
    # Importiruem obe funktsii, kak v pervom fayle
    from modules.self.spread_guard import status as _status, evaluate as _eval  # type: ignore
except Exception:
    # Obrabatyvaem oshibki dlya obeikh peremennykh
    _status = _eval = None  # type: ignore

def register(app):
    app.register_blueprint(bp_spread)

# Dobavlyaem marshrut /status iz pervogo fayla
@bp_spread.route("/spread/guard/status", methods=["GET"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"spread_guard unavailable"}), 500
    return jsonify(_status())

# Ispolzuem marshrut /evaluate
@bp_spread.route("/spread/guard/evaluate", methods=["POST"])
def api_eval():
    if _eval is None: return jsonify({"ok": False, "error":"spread_guard unavailable"}), 500
    d = request.get_json(True, True) or {}
# return jsonify(_eval(list(d.get("targets") or [])))