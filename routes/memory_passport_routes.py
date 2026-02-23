# -*- coding: utf-8 -*-
"""
routes/memory_passport_routes.py - REST: paketnoe prostavlenie «profileov» pamyati.

Mosty:
- Yavnyy: (Veb ↔ Memory) edinaya knopka «prostavit/pochinit provenance».
- Skrytyy #1: (Audit ↔ Prozrachnost) dry-run cherez A/B.
- Skrytyy #2: (RAG ↔ Dedup) kheshi prigodyatsya dlya poiska/sshivki.

Zemnoy abzats:
Odna ruchka - i na polkakh pamyati est shtamp «kto/chto/kogda».

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_mem_pass = Blueprint("mem_passport", __name__)

try:
    from modules.memory.passport import sweep as _sweep  # type: ignore
except Exception:
    _sweep = None  # type: ignore

def register(app):
    app.register_blueprint(bp_mem_pass)

@bp_mem_pass.route("/mem/passport/sweep", methods=["POST"])
def api_sweep():
    if _sweep is None: return jsonify({"ok": False, "error":"passport unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_sweep(str(d.get("query","*")), int(d.get("limit",200))))
# c=a+b