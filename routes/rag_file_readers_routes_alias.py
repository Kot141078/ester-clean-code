# -*- coding: utf-8 -*-
"""
routes/rag_file_readers_routes_alias.py

Naznachenie:
- Dat upravlyaemyy HTTP-dostup k lokalnym dokumentam dlya RAG
  bez izmeneniya suschestvuyuschikh RAG-endpointov.
- Vsya logika optsionalna i vklyuchaetsya tolko pri RAG_ENABLE=1.

Endpointy:
- GET  /ester/rag/docs/ping      -> {ok, enabled, docs_path}
- GET  /ester/rag/docs/list      -> {ok, items:[{path,size}]}
- POST /ester/rag/docs/ingest    -> {ok, total, ingested}

Kontrakty ne lomayut suschestvuyuschiy /compat/chat/rag_*, tolko dobavlyayut
vspomogatelnye tochki.

Mosty:
- Yavnyy: HTTP -> modules.rag.file_readers.ingest_all
- Skrytyy #1: ENV (RAG_ENABLE, RAG_DOCS_PATH) -> povedenie marshrutov
- Skrytyy #2: RAG-khab (modules.rag.hub) obschiy dlya ostalnoy sistemy

Zemnoy abzats:
Eto servisnyy lift dlya knig: taskaet dokumenty v indeks po zaprosu,
ne trogaya glavnyy vkhod posetiteley.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, current_app, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.rag import file_readers
except Exception:  # pragma: no cover
    file_readers = None  # type: ignore


def _enabled() -> bool:
    return os.getenv("RAG_ENABLE", "0") in {"1", "true", "True"}


def _docs_path() -> str:
    return os.getenv("RAG_DOCS_PATH", "").strip()


def create_blueprint() -> Blueprint:
    bp = Blueprint("ester-rag-docs", __name__, url_prefix="/ester/rag/docs")

    @bp.get("/ping")
    def ping() -> Any:
        return jsonify(
            {
                "ok": True,
                "enabled": bool(_enabled()),
                "docs_path": _docs_path() or None,
            }
        )

    @bp.get("/list")
    def list_docs() -> Any:
        if not _enabled():
            return jsonify({"ok": False, "reason": "rag_disabled"}), 400
        if file_readers is None:
            return jsonify({"ok": False, "reason": "no_file_readers"}), 500

        items = file_readers.list_docs()
        return jsonify({"ok": True, "items": items})

    @bp.post("/ingest")
    def ingest() -> Any:
        if not _enabled():
            return jsonify({"ok": False, "reason": "rag_disabled"}), 400
        if file_readers is None:
            return jsonify({"ok": False, "reason": "no_file_readers"}), 500

        tag = (request.json or {}).get("tag") if request.is_json else None
        if not isinstance(tag, str) or not tag.strip():
            tag = "local_docs"

        res = file_readers.ingest_all(tag=tag)
        code = 200 if res.get("ok") else 500
        return jsonify(res), code

    return bp


def register(app) -> None:
    """Registriruet blueprint, esli esche ne zaregistrirovan."""
    bp = create_blueprint()
    name = bp.name

    if getattr(app, "blueprints", None) and name in app.blueprints:
        return

    app.register_blueprint(bp)
    try:
        print("[ester-rag-docs/routes] registered /ester/rag/docs/*")
    except Exception:
        pass


def init_app(app) -> None:  # pragma: no cover
    register(app)


__all__ = ["create_blueprint", "register", "init_app"]