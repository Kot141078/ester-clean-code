# -*- coding: utf-8 -*-
"""routes/mem_prov_routes.py - REST: /mem/prov/*

Mosty:
- Yavnyy: (Veb ↔ Memory) upravlenie i status provenansa.
- Skrytyy #1: (Passport ↔ Audit) zhurnal JSONL - chitaem chelovekoponyatno.
- Skrytyy #2: (KG/Linker ↔ Kontekst) istochniki prigodyatsya pri linkovke.

Zemnoy abzats:
Vidim, prikruchen li “stamp” k pamyati, i skolko raz on srabotal.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("mem_prov_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.mem.provenance_patch import status as _st, enable as _en  # type: ignore
except Exception:
    _st=_en=None  # type: ignore

@bp.route("/mem/prov/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error":"prov_unavailable"}), 500
    return jsonify(_st())

@bp.route("/mem/prov/enable", methods=["POST"])
def api_enable():
    if _en is None: return jsonify({"ok": False, "error":"prov_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_en(bool(d.get("enable", True))))
# c=a+b