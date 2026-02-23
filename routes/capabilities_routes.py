# -*- coding: utf-8 -*-
"""
routes/capabilities_routes.py - REST: spisok vozmozhnostey i deklaratsii.

Mosty:
- Yavnyy: (Veb ↔ Samosoznanie) bystryy spisok «chto dostupno».
- Skrytyy #1: (Plan ↔ Volya) na osnove spiska stroyatsya stsenarii.
- Skrytyy #2: (Panel ↔ UX) mozhno pokazat polzovatelyu bez lezviya v kod.

Zemnoy abzats:
Spravochnik dostupnykh rychagov.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_cap = Blueprint("capabilities_routes", __name__)

try:
    from modules.capabilities.registry import list_caps as _list, declare as _decl  # type: ignore
except Exception:
    _list=_decl=None  # type: ignore

def register(app):
    app.register_blueprint(bp_cap)

@bp_cap.route("/capabilities/list", methods=["GET"])
def api_list():
    if _list is None: return jsonify({"ok": False, "error":"cap_unavailable"}), 500
    return jsonify(_list())

@bp_cap.route("/capabilities/declare", methods=["POST"])
def api_decl():
    if _decl is None: return jsonify({"ok": False, "error":"cap_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_decl(str(d.get("name","")), str(d.get("kind","")), str(d.get("desc",""))))
# c=a+b