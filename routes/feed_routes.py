# -*- coding: utf-8 -*-
"""routes/feed_routes.py - publichnyy fid dlya UI: /feed/latest.
Sources:
  1) StructuredMemory.flashback (by tag i zaprosu)
  2) Telegram feed (fallback) - modules.telegram_feed_store.latest
Registration:
  from routes.feed_routes import register_feed_routes
  register_feed_routes(app, url_prefix="/feed")"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Set

from flask import jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _build_mm():
    from cards_memory import CardsMemory  # type: ignore
    from memory_manager import MemoryManager  # type: ignore
    from structured_memory import StructuredMemory  # type: ignore
    from vector_store import VectorStore  # type: ignore

    persist_dir = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(persist_dir, exist_ok=True)
    vstore = VectorStore(
        collection_name=os.getenv("COLLECTION_NAME", "ester_store"),
        persist_dir=persist_dir,
        use_embeddings=bool(int(os.getenv("USE_EMBEDDINGS", "0"))),
        embeddings_api_base=os.getenv("EMBEDDINGS_API_BASE", ""),
        embeddings_model=os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        embeddings_api_key=os.getenv("EMBEDDINGS_API_KEY", ""),
        use_local=bool(int(os.getenv("EMBEDDINGS_USE_LOCAL", "1"))),
    )
    structured = StructuredMemory(os.path.join(persist_dir, "structured_mem", "store.json"))  # type: ignore
    cards = CardsMemory(os.path.join(persist_dir, "ester_cards.json"))  # type: ignore
    return MemoryManager(vstore, structured, cards)  # type: ignore


def _parse_tags_csv(s: str) -> Set[str]:
    parts = [p.strip() for p in (s or "").split(",")]
    return {p for p in parts if p}


def register_feed_routes(app, url_prefix: str = "/feed"):
    def _mm():
        if getattr(app, "memory_manager", None) is not None:
            return app.memory_manager  # type: ignore[attr-defined]
        mm = _build_mm()
        setattr(app, "memory_manager", mm)
        return mm

    @app.get(url_prefix + "/latest")
    @jwt_required(optional=True)
    def feed_latest():
        limit = max(1, min(int(request.args.get("limit", "20")), 100))
        q = (request.args.get("q") or "*").strip()
        tags_csv = request.args.get("tags", "")
        req_tags = _parse_tags_csv(tags_csv)
        # Trying from memory
        items: List[Dict[str, Any]] = []
        try:
            hits = _mm().flashback(query=q, k=min(5 * limit, 200))  # type: ignore[attr-defined]
        except Exception:
            hits = []
        for h in hits:
            ht = (h.get("tags") or []) if isinstance(h.get("tags"), list) else []
            htset = {str(t) for t in ht}
            if req_tags and req_tags.isdisjoint(htset):
                continue
            items.append(
                {
                    "id": h.get("id"),
                    "text": h.get("text"),
                    "tags": list(htset),
                    "weight": h.get("weight", 0.0),
                }
            )
            if len(items) >= limit:
                break
        # If empty, take it from Telegram fed
        if not items:
            try:
                from modules.telegram_feed_store import latest as tg_latest  # type: ignore

                tg = tg_latest(limit=limit)
                for e in tg:
                    tt = e.get("tags") or []
                    if req_tags and req_tags.isdisjoint(set(tt)):
                        continue
                    items.append(
                        {
                            "id": f"tg_{e.get('chat_id')}_{e.get('message_id')}",
                            "text": e.get("text") or "",
                            "tags": list(tt) + ["tg"],
                            "weight": 0.5,
                        }
                    )
                    if len(items) >= limit:
                        break
            except Exception:
                pass
# return jsonify({"ok": True, "items": items, "limit": limit, "q": q, "tags": list(req_tags)})


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
def register(app):
    # calls an existing register_fed_rutes(app) (url_prefix is ​​taken by default inside the function)
    return register_feed_routes(app)

# === /AUTOSHIM ===