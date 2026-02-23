# -*- coding: utf-8 -*-
"""
/reflect/* — marshruty «refleksii»: svyazyvayut zapros s pamyatyu i RAG-kontekstom.
- POST /reflect/run {query, k?}
- GET  /reflect/ping
"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _gather_context(vstore, query: str, k: int = 5) -> List[Dict[str, Any]]:
    try:
        return vstore.search(query, k=k)
    except Exception:
        return []


def register_reflection_routes(app, vstore, memory_manager, url_prefix: str = "/reflect"):
    bp = Blueprint("reflect", __name__)

    @bp.get(url_prefix + "/ping")
    def reflect_ping():
        return jsonify({"ok": True})

    @bp.post(url_prefix + "/run")
    @jwt_required()
    def reflect_run():
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        query = (data.get("query") or "").strip()
        if not query:
            return jsonify({"ok": False, "error": "query required"}), 400
        k = int(data.get("k", 5))
        ctx = _gather_context(vstore, query, k)
        fb = memory_manager.flashback(query, k=k)
        summary = f"Refleksiya po zaprosu: «{query}». Naydeno kontekstov: {len(ctx)}, fleshbekov: {len(fb)}."
        return jsonify({"ok": True, "summary": summary, "context": ctx, "flashback": fb})

# app.register_blueprint(bp)