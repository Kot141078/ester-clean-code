# -*- coding: utf-8 -*-
"""routes/research_routes.py - async-agent /research/search.
Naznachenie: parallelnyy opros pamyati i podgotovka “issledovatelskoy” vyborki.

Registration:
  from routes.research_routes import register_research_routes
  register_research_routes(app, url_prefix="/research")

Mosty:
- Yavnyy: (Memory ↔ Web) bystryy REST-dostup k flashback i svodke.
- Skrytyy #1: (Infoteoriya ↔ Shum) szhatie konteksta v kratkuyu svodku snizhaet noise.
- Skrytyy #2: (Kibernetika ↔ Obratnaya svyaz) determinirovannye otvety/taym-aut - ustoychivost payplaynov.
- Skrytyy #3: (Logika ↔ Kontrakty) strogaya skhema vkhoda/vykhoda delaet route prigodnym dlya avtomatov.

Zemnoy abzats:
Dumay o module kak o “poiskovom endoskope”: tonko, bystro i bezopasno dostaem kusochki pamyati,
a zatem szhato opisyvaem kartinu, chtoby operatoru bylo vidno glavnoe.

c=a+b"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, List

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


async def _search_flashback(mm, query: str, k: int) -> List[Dict[str, Any]]:
    """Calling a potentially blocking method is taken into the thread."""
    def _call():
        try:
            return mm.flashback(query=query, k=k)  # type: ignore[attr-defined]
        except Exception:
            return []

    return await asyncio.to_thread(_call)


async def _mock_agent_summarize(hits: List[Dict[str, Any]], timeout: float) -> str:
    """Naive summary: take the first fragments of text and glue them into a line."""
    async def _do():
        parts = []
        for h in hits[:8]:
            t = (h.get("text") or "").strip()
            if t:
                parts.append(t.split("\n")[0][:200])
        if not parts:
            return "Insufficient context for summary."
        return " · ".join(parts)[:1000]

    return await asyncio.wait_for(_do(), timeout=timeout)


def register_research_routes(app, url_prefix: str = "/research"):
    """Registration of memory research routes."""
    def _mm():
        if getattr(app, "memory_manager", None) is not None:
            return app.memory_manager  # type: ignore[attr-defined]
        mm = _build_mm()
        setattr(app, "memory_manager", mm)
        return mm

    def _run_search(query: str, labels: List[str], k: int) -> Dict[str, Any]:
        t0 = time.time()
        mm = _mm()
        try:
            hits = mm.flashback(query=query, k=min(max(int(k or 1), 1), 200))  # type: ignore[attr-defined]
        except Exception:
            hits = []
        if labels:
            lblset = {str(x) for x in labels}
            hits = [h for h in hits if (set((h.get("tags") or [])) & lblset)]

        items = []
        for h in hits[:k]:
            items.append(
                {
                    "id": h.get("id"),
                    "text": (h.get("text") or "")[:400],
                    "tags": h.get("tags") or [],
                    "weight": h.get("weight", 0.0),
                    "score": h.get("score", 0.0),
                }
            )
        summary_parts = [str(it.get("text") or "").strip() for it in items[:5] if str(it.get("text") or "").strip()]
        summary = " · ".join(summary_parts)[:1000] if summary_parts else "Insufficient context for summary."
        took = int((time.time() - t0) * 1000)
        return {
            "ok": True,
            "query": query,
            "results": items,
            "items": items,
            "summary": summary,
            "took_ms": took,
        }

    @app.get(url_prefix + "/search")
    @jwt_required()
    def research_search_get():
        query = (request.args.get("query") or "").strip()
        if not query:
            return jsonify({"ok": False, "error": "empty query"}), 400
        labels_raw = request.args.get("labels", "")
        labels = [x.strip() for x in str(labels_raw).split(",") if x.strip()]
        try:
            k = int(request.args.get("k", "50"))
        except Exception:
            k = 50
        return jsonify(_run_search(query=query, labels=labels, k=max(1, k)))

    @app.post(url_prefix + "/search")
    @jwt_required()
    def research_search():
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        query = (data.get("query") or "").strip()
        if not query:
            return jsonify({"ok": False, "error": "empty query"}), 400
        labels = data.get("labels") or []
        try:
            k = int(data.get("k") or 50)
        except Exception:
            k = 50
        labels2 = labels if isinstance(labels, list) else []
        return jsonify(_run_search(query=query, labels=labels2, k=max(1, k)))


__all__ = ["register_research_routes"]
# c=a+b


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
def register(app):
    # calls an existing registry_research_rust(app) (url_prefix is ​​taken by default inside the function)
    return register_research_routes(app)

# === /AUTOSHIM ===
