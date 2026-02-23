# -*- coding: utf-8 -*-
"""
routes/mem_provenance_routes.py — HTTP-ruchki dlya obogascheniya pamyati edinym «profileom znaniya».

Endpointy:
  • POST /mem/provenance/ensure  {"items":[{...}], "source":{...}} v†' {"items":[...]} s meta.provenance

Mosty:
- Yavnyy: (Memory v†" Audit) edinyy profile oblegchaet dedup/sravnenie/obmen mezhdu uzlami.
- Skrytyy #1: (Infoteoriya v†" Set) sha256 sovmestim s setevymi «profileami znaniy».
- Skrytyy #2: (Kibernetika v†" Kontrol) yavnaya ruchka dlya massovogo obogascheniya bez izmeneniya starykh kontraktov.

Zemnoy abzats:
Eto «shtempelevka»: podash pachku kartochek — vernutsya so shtampom «kto/kogda/chto».

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_mem_prov = Blueprint("mem_provenance", __name__)

try:
    from modules.memory.provenance_unified import ensure_many  # type: ignore
except Exception:
    ensure_many = None  # type: ignore

def register(app):
    app.register_blueprint(bp_mem_prov)

@bp_mem_prov.route("/mem/provenance/ensure", methods=["POST"])
def api_ensure_provenance():
    if ensure_many is None:
        return jsonify({"ok": False, "error": "provenance_unified unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    items: List[Dict[str, Any]] = list(data.get("items") or [])
    source: Dict[str, Any] = dict(data.get("source") or {})
    out = ensure_many(items, default_source=source)
# return jsonify({"ok": True, "items": out})