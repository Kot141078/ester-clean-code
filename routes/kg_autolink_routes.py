# -*- coding: utf-8 -*-
"""
routes/kg_autolink_routes.py - REST: avtolink suschnostey i statistika KG.

Mosty:
- Yavnyy: (Veb ↔ KG) daet prostoy API dlya svyazi pamyati i grafa.
- Skrytyy #1: (Gipotezy ↔ Uzly) downstream-moduli berut node_id iz otveta.
- Skrytyy #2: (RAG ↔ Navigatsiya) uzly stanovyatsya «yakoryami» dlya poiska.

Zemnoy abzats:
«Nashel imena - zavel kartochki - svyazal s pamyatyu». Prostoy shag, kotoryy usilivaet posleduyuschiy poisk i sintez.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("kg_autolink_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.mem.entity_linker import autolink as _autolink  # type: ignore
    from modules.kg.shadow import stats as _kg_stats  # type: ignore
except Exception:
    _autolink=_kg_stats=None  # type: ignore

@bp.route("/mem/kg/autolink", methods=["POST"])
def api_autolink():
    if _autolink is None: return jsonify({"ok": False, "error":"kg_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_autolink(list(d.get("items") or []), list(d.get("tags") or [])))

@bp.route("/mem/kg/stats", methods=["GET"])
def api_stats():
    if _kg_stats is None: return jsonify({"ok": False, "error":"kg_unavailable"}), 500
    return jsonify(_kg_stats())
# c=a+b