# -*- coding: utf-8 -*-
"""
routes/aid_routes.py - REST dlya ekstrennoy pomoschi Pape: kontakty/nastroyki, SOS-plan/trigger, fin.-obnaruzhenie.

Mosty:
- Yavnyy: (Volya ↔ Deystviya) prostye ruchki dlya upravleniya zabotoy o Pape.
- Skrytyy #1: (Prioritet ↔ Kontrol) integratsiya s papinymi modulyami (prioritet, «tabletki») - bez izmeneniya kontraktov.
- Skrytyy #2: (UX ↔ Prozrachnost) panel /admin/aid s bystrymi knopkami (plan, simulyatsiya, trigger).

Zemnoy abzats:
Eto «krasnaya papka»: knopka SOS, spisok kontaktov i chek-listy - vse v odnom meste.

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, jsonify, request, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_aid = Blueprint("aid", __name__, template_folder="../templates", static_folder="../static")

try:
    from modules.aid.contacts import get_all as _get_all, add as _add, verify as _verify, set_prefs as _set_prefs  # type: ignore
    from modules.aid.emergency import plan_sos as _plan_sos, simulate as _simulate, trigger as _trigger  # type: ignore
    from modules.aid.fin_discovery import start as _fin_start, status as _fin_status  # type: ignore
except Exception:
    _get_all = _add = _verify = _set_prefs = None  # type: ignore
    _plan_sos = _simulate = _trigger = None  # type: ignore
    _fin_start = _fin_status = None  # type: ignore

def register(app):
    app.register_blueprint(bp_aid)

# kontakty/nastroyki
@bp_aid.route("/aid/contacts", methods=["GET"])
def api_contacts():
    if _get_all is None: return jsonify({"ok": False, "error":"aid module unavailable"}), 500
    return jsonify(_get_all())

@bp_aid.route("/aid/contacts/add", methods=["POST"])
def api_add_contact():
    if _add is None: return jsonify({"ok": False, "error":"aid module unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(_add(str(d.get("kind","")), str(d.get("name","")), str(d.get("channel","")), str(d.get("value","")), int(d.get("priority",5)), str(d.get("note",""))))

@bp_aid.route("/aid/contacts/verify", methods=["POST"])
def api_verify_contact():
    if _verify is None: return jsonify({"ok": False, "error":"aid module unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(_verify(str(d.get("id","")), str(d.get("code",""))))

@bp_aid.route("/aid/preferences", methods=["POST"])
def api_prefs():
    if _set_prefs is None: return jsonify({"ok": False, "error":"aid module unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(_set_prefs(**d))

# SOS/eskalatsii
@bp_aid.route("/aid/sos", methods=["POST"])
def api_sos():
    if _plan_sos is None: return jsonify({"ok": False, "error":"aid module unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(_plan_sos(str(d.get("situation","")), str(d.get("location_hint","")), d.get("country")))

@bp_aid.route("/aid/simulate", methods=["POST"])
def api_sim():
    if _simulate is None: return jsonify({"ok": False, "error":"aid module unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(_simulate(str(d.get("situation","")), str(d.get("level","medium"))))

@bp_aid.route("/aid/trigger", methods=["POST"])
def api_trig():
    if _trigger is None: return jsonify({"ok": False, "error":"aid module unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(_trigger(d.get("plan") or {}))

# finansy (myagkoe obnaruzhenie)
@bp_aid.route("/aid/fin/discovery/start", methods=["POST"])
def api_fin_start():
    if _fin_start is None: return jsonify({"ok": False, "error":"aid module unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(_fin_start(str(d.get("scope","basic"))))

@bp_aid.route("/aid/fin/discovery/status", methods=["GET"])
def api_fin_status():
    if _fin_status is None: return jsonify({"ok": False, "error":"aid module unavailable"}), 500
    return jsonify(_fin_status())

# panel
@bp_aid.route("/admin/aid", methods=["GET"])
def admin_aid():
    return render_template("aid_console.html")
# c=a+b