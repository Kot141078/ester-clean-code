# -*- coding: utf-8 -*-
"""
routes/cautious_freedom_routes.py - REST: status/nastroyka politiki, «tabletka», khartiya.

Mosty:
- Yavnyy: (Volya ↔ Kontrol) operator upravlyaet urovnem ostorozhnosti bez pravok suschestvuyuschikh marshrutov.
- Skrytyy #1: (UX ↔ Prozrachnost) vse vidno i nastraivaetsya v odnom meste.
- Skrytyy #2: (Memory ↔ Etos) khesh «khartii» - neizmenyaemaya otsylka k iznachalnomu smyslu.

Zemnoy abzats:
Eto schit i regulyator: naskolko «tugo» krutit ostorozhnost i na skolko minut vydavat «propusk».

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, jsonify, request, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_caution = Blueprint("cautious_freedom", __name__, template_folder="../templates", static_folder="../static")

try:
    from modules.policy.cautious_freedom import status as _status, set_state as _set_state, pill_set as _pill_set, charter as _charter  # type: ignore
except Exception:
    _status = _set_state = _pill_set = _charter = None  # type: ignore

def register(app):
    app.register_blueprint(bp_caution)

@bp_caution.route("/policy/caution/status", methods=["GET"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"caution policy unavailable"}), 500
    return jsonify(_status())

@bp_caution.route("/policy/caution/set", methods=["POST"])
def api_set():
    if _set_state is None: return jsonify({"ok": False, "error":"caution policy unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    enabled = d.get("enabled", None)
    risk_tolerance = d.get("risk_tolerance", None)
    return jsonify(_set_state(enabled, risk_tolerance))

@bp_caution.route("/policy/caution/pill", methods=["POST"])
def api_pill():
    if _pill_set is None: return jsonify({"ok": False, "error":"caution policy unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    arm = bool(d.get("arm", True)); ttl = int(d.get("ttl_sec", 300))
    return jsonify(_pill_set(arm, ttl))

@bp_caution.route("/policy/caution/charter", methods=["GET"])
def api_charter():
    if _charter is None: return jsonify({"ok": False, "error":"caution policy unavailable"}), 500
    return jsonify(_charter())

@bp_caution.route("/admin/safety", methods=["GET"])
def admin_safety():
    return render_template("safety_console.html")
# c=a+b