# -*- coding: utf-8 -*-
"""routes/caution_routes.py - REST: politika, vydacha/otzyv "pilyul".

Mosty:
- Yavnyy: (Veb ↔ Soglasie) upravlyaem tokenami i smotrim politiku.
- Skrytyy #1: (Audit ↔ Prozrachnost) est spisok i otzyv.
- Skrytyy #2: (Integratsiya ↔ Panel) druzhit s HTML-panelyu AppOps+.

Zemnoy abzats:
Knopka “podtverdit risk”: poluchil zheton, vypolnil, otozval.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import json, os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_caution = Blueprint("caution_routes", __name__)

MERGED = os.getenv("APP_POLICY_MERGED","data/policy/caution_rules.merged.json")

try:
    from modules.ops.consent import issue as _issue, revoke as _revoke, list_tokens as _list  # type: ignore
except Exception:
    _issue = _revoke = _list = None  # type: ignore

def register(app):
    app.register_blueprint(bp_caution)

@bp_caution.route("/caution/policy", methods=["GET"])
def api_policy():
    try:
        return jsonify(json.load(open(MERGED,"r",encoding="utf-8")))
    except Exception:
        return jsonify({"rules": [], "note":"merged policy not found"})

@bp_caution.route("/caution/pill/issue", methods=["POST"])
def api_issue():
    if _issue is None: return jsonify({"ok": False, "error":"consent unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_issue(str(d.get("pattern","^$")), str(d.get("method","GET")), int(d.get("ttl",0) or 0), str(d.get("note",""))))

@bp_caution.route("/caution/pill/revoke", methods=["POST"])
def api_revoke():
    if _revoke is None: return jsonify({"ok": False, "error":"consent unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_revoke(str(d.get("token",""))))

@bp_caution.route("/caution/pill/list", methods=["GET"])
def api_list():
    if _list is None: return jsonify({"ok": False, "error":"consent unavailable"}), 500
    return jsonify(_list())
# c=a+b