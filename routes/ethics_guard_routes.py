# -*- coding: utf-8 -*-
"""
routes/ethics_guard_routes.py - REST: otsenka namereniy i pravila.

Mosty:
- Yavnyy: (Veb ↔ Etika) prostoy API dlya vsekh moduley.
- Skrytyy #1: (Panel ↔ Operator) udobno proveryat spornye deystviya.
- Skrytyy #2: (Kvorum ↔ Resheniya) mozhno zaprashivat kvorum dlya «warn».

Zemnoy abzats:
Prezhde chem delat - sprosili «mozhno?».

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_eth = Blueprint("ethics_guard", __name__)

try:
    from modules.ethics.guard import assess as _assess, load_rules as _rules  # type: ignore
except Exception:
    _assess=_rules=None  # type: ignore

def register(app):
    app.register_blueprint(bp_eth)

@bp_eth.route("/ethics/assess", methods=["POST"])
def api_assess():
    if _assess is None: return jsonify({"ok": False, "error":"ethics_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_assess(str(d.get("intent","")), d.get("context") or {}))

@bp_eth.route("/ethics/rules", methods=["GET"])
def api_rules():
    if _rules is None: return jsonify({"ok": False, "error":"ethics_unavailable"}), 500
    return jsonify({"ok": True, "rules": _rules()})
# c=a+b