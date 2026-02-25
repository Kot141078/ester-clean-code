# -*- coding: utf-8 -*-
"""routes/consent_routes.py - REST+UI dlya lokalnogo protokola razresheniy.

Ruchki:
  POST /consent/mode {"mode":"ask_always|remember_ttl|deny_all"}
  POST /consent/request {"scope":"mix_apply","target":"Notepad","meta":{...}} -> {decision:"allow|deny|ask",ticket_id?}
  POST /consent/decide {"ticket_id":"...","allow":true,"ttl_sec":60}
  GET /admin/consent -> UI

Recommendations integratsii:
- Pered chuvstvitelnym deystviem vyzyvat /consent/request; pri decision="ask" - vsplyvayuschaya kartochka v UI.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.security.consent_protocol import set_mode, request as c_request, decide as c_decide
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("consent_routes", __name__, url_prefix="/consent")

@bp.route("/mode", methods=["POST"])
def mode():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(set_mode(data.get("mode","ask_always")))

@bp.route("/request", methods=["POST"])
def req():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(c_request(data.get("scope",""), data.get("target",""), data.get("meta") or {}))

@bp.route("/decide", methods=["POST"])
def dec():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(c_decide(data.get("ticket_id",""), bool(data.get("allow", False)), int(data.get("ttl_sec", 0))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_consent.html")

def register(app):
    app.register_blueprint(bp)