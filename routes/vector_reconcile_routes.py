# -*- coding: utf-8 -*-
"""routes/vector_reconcile_routes.py - HTTP dlya obmena vektornymi elementsami.

Endpoint:
  • GET /mem/vector/export?limit=50 — vydat poslednie elementy (summary+truncated transcript)
  • POST /mem/vector/reconcile — prinyat batch {items:[{id,text,tags,meta},...]}

Mosty:
- Yavnyy: (Memory v†" Set) prosteyshiy obmen mezhdu uzlami bez vneshnikh zavisimostey.
- Skrytyy #1: (Infoteoriya v†" Nadezhnost) esli stor nedostupen - ne teryaem, pishem v fallback-ochered.
- Skrytyy #2: (Kibernetika v†" Masshtab) limit/batchi pozvolyayut dozirovat trafik.

Zemnoy abzats:
Eto “vorota sklada”: otdat spisok korobok sosedu, prinyat ego korobki i razlozhit.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_vec_reconcile = Blueprint("vec_reconcile", __name__)

try:
    from modules.memory.vector_reconcile import export_recent, reconcile  # type: ignore
except Exception:
    def export_recent(limit=50): return []  # type: ignore
    def reconcile(items): return {"ok": False, "error": "vector_reconcile not available"}  # type: ignore

def register(app):
    app.register_blueprint(bp_vec_reconcile)

@bp_vec_reconcile.route("/mem/vector/export", methods=["GET"])
def api_export():
    try:
        limit = int(request.args.get("limit", "50"))
    except Exception:
        limit = 50
    return jsonify({"ok": True, "items": export_recent(limit=limit)})

@bp_vec_reconcile.route("/mem/vector/reconcile", methods=["POST"])
def api_reconcile():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    items: List[Dict[str, Any]] = list(data.get("items") or [])
    return jsonify(reconcile(items))
