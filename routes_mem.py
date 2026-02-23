# -*- coding: utf-8 -*-
"""
Routes for Memory: /mem — flashback/alias/compact.
Sovmestimo s kanonom: register_mem_routes(app, cards, url_prefix="/mem")
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from flask import current_app, jsonify, request
from flask_jwt_extended import jwt_required
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _mm_from_args(app) -> Optional[Any]:
    return getattr(app, "memory_manager", None)


def _flashback(memory_manager, query: str, k: int = 8) -> Dict[str, Any]:
    bundle = memory_manager.flashback(user="*", query=query, k=k)
    return {"items": bundle.get("items", []), "stats": bundle.get("stats", {})}


def _alias(memory_manager, doc_id: str, new_id: str) -> Dict[str, Any]:
    return memory_manager.alias_doc_id(doc_id, new_id)


def _compact(memory_manager, dry_run: bool = True) -> Dict[str, Any]:
    return memory_manager.compact(dry_run=dry_run)


def register_mem_routes(app, cards, url_prefix: str = "/mem"):
    @app.get(url_prefix + "/flashback")
    @jwt_required()
    def mem_flashback():
        query = request.args.get("q", "") or request.args.get("query", "")
        k = int(request.args.get("k", "8"))
        mm = _mm_from_args(current_app)
        if mm is None:
            return jsonify({"error": "memory_manager not available"}), 503
        try:
            bundle = _flashback(mm, query, k)
            return jsonify(bundle)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post(url_prefix + "/alias")
    @jwt_required()
    def mem_alias():
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        doc_id = str(data.get("doc_id") or data.get("old_doc_id") or "")
        new_id = str(data.get("new_id") or data.get("new_doc_id") or "")
        if not doc_id or not new_id:
            return jsonify({"error": "doc_id/new_id required"}), 400
        mm = _mm_from_args(current_app)
        if mm is None:
            return jsonify({"error": "memory_manager not available"}), 503
        res = _alias(mm, doc_id, new_id)
        code = 200 if res.get("ok") else 400
        return jsonify(res), code

    @app.post(url_prefix + "/compact")
    @jwt_required()
    def mem_compact():
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        dry = bool(data.get("dry_run", True))
        mm = _mm_from_args(current_app)
        if mm is None:
            return jsonify({"error": "memory_manager not available"}), 503
        res = _compact(mm, dry)
# return jsonify(res), (200 if res.get("ok") else 500)