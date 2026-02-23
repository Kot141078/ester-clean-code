# -*- coding: utf-8 -*-
"""
routes/mm_guard_routes.py - REST: audit get_mm i flag podozreniy.

Mosty:
- Yavnyy: (Veb ↔ Memory) vydaet metriki i prinimaet signaly ot lintera.
- Skrytyy #1: (SelfCatalog ↔ Prozrachnost) vidno, kto chasche vsego beret dostup k pamyati.
- Skrytyy #2: (Ostorozhnost ↔ Intsidenty) flagi pomogayut rassledovat problemy.

Zemnoy abzats:
Eto kak zhurnal na prokhodnoy: skolko lyudey proshlo v khranilische i kto pytalsya «cherez okno».

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("mm_guard_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.mm.guard import status as _st, flag_bypass as _flag  # type: ignore
except Exception:
    _st=_flag=None  # type: ignore

@bp.route("/mm/audit/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error":"mm_guard_unavailable"}), 500
    return jsonify(_st())

@bp.route("/mm/audit/flag", methods=["POST"])
def api_flag():
    if _flag is None: return jsonify({"ok": False, "error":"mm_guard_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_flag(str(d.get("path","")), str(d.get("reason","manual_flag"))))
# c=a+b