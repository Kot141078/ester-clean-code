# -*- coding: utf-8 -*-
"""routes/consent_policy_routes.py - REST+UI dlya policy soglasiy.

Ruchki:
  GET /policy/list
  POST /policy/upsert {"scope":"hotkey","title":"BankApp","decision":"deny","ttl":0}
  POST /policy/remove {"index":0}
  POST /policy/decide {"scope":"mix_apply","title":"Notepad"} -> {"decision":"allow|deny|ask|pass","ttl"?:int}
  GET /admin/policy

Integratsia:
- Pered vyzovami, trebuyuschimi soglasiya, sperva sprashivayte /policy/decide; esli pass - ispolzuyte /consent/request.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.security.consent_policy import list_rules, upsert, remove, decide
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("consent_policy_routes", __name__, url_prefix="/policy")

@bp.route("/list", methods=["GET"])
def lst():
    return jsonify({"ok": True, "rules": list_rules()})

@bp.route("/upsert", methods=["POST"])
def ups():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(upsert(data))

@bp.route("/remove", methods=["POST"])
def rem():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(remove(int(data.get("index", -1))))

@bp.route("/decide", methods=["POST"])
def dec():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(decide(data.get("scope",""), data.get("title","")))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_policy.html")

def register(app):
    app.register_blueprint(bp)