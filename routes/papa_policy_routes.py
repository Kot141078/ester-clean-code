# -*- coding: utf-8 -*-
"""
routes/papa_policy_routes.py - REST dlya politiki prioriteta Papy (vesa i «tabletka»).

Mosty:
- Yavnyy: (Volya ↔ Kontrol) vklyuchaem/nastraivaem silu prioriteta.
- Skrytyy #1: (Ekonomika ↔ Plany) planirovschiki mogut «sprosit» vesa cherez eti ruchki.
- Skrytyy #2: (UX ↔ Prozrachnost) prostaya, izolirovannaya tochka upravleniya.

Zemnoy abzats:
Ruchka gromkosti i knopka «na vsyakiy sluchay» - bez nee sistema tikhaya i predskazuemaya.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_papa_pol = Blueprint("papa_policy", __name__)

try:
    from modules.policy.papa_priority import status as _status, set_policy as _set, pill as _pill  # type: ignore
except Exception:
    _status = _set = _pill = None  # type: ignore

def register(app):
    app.register_blueprint(bp_papa_pol)

@bp_papa_pol.route("/policy/papa/status", methods=["GET"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"papa_policy unavailable"}), 500
    return jsonify(_status())

@bp_papa_pol.route("/policy/papa/set", methods=["POST"])
def api_set():
    if _set is None: return jsonify({"ok": False, "error":"papa_policy unavailable"}), 500
    d = (request.get_json(True, True) or {})
    return jsonify(_set(d.get("priority"), d.get("money_bias"), d.get("task_bias")))

@bp_papa_pol.route("/policy/papa/pill", methods=["POST"])
def api_pill():
    if _pill is None: return jsonify({"ok": False, "error":"papa_policy unavailable"}), 500
    d = (request.get_json(True, True) or {})
    arm = bool(d.get("arm", True)); ttl = int(d.get("ttl_sec", 300))
    return jsonify(_pill(arm, ttl))
# c=a+b