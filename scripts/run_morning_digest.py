# -*- coding: utf-8 -*-
"""scripts/run_morning_digest.py - CLI dlya odnorazovogo zapuska utrennego daydzhesta.

Primery:
  python scripts/run_morning_digest.py
  MORNING_HOUR=0 MORNING_WINDOW_MIN=1440 python scripts/run_morning_digest.py # prinuditelno “v window”

Vyvodit JSON s resultatom (channel: telegram/email/preview)."""
from __future__ import annotations

import json
import os

try:
    from app import app as flask_app  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit(f"Cannot import Flask app: {e}")

from proactive_notifier import MorningDigestDaemon  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _persist_dir() -> str:
    pd = os.getenv("PERSIST_DIR")
    if pd:
        os.makedirs(pd, exist_ok=True)
        return pd
    pd = os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(pd, exist_ok=True)
    return pd


def _build_mm():
    if getattr(flask_app, "memory_manager", None) is not None:
        return flask_app.memory_manager  # type: ignore[attr-defined]
    from cards_memory import CardsMemory  # type: ignore
    from memory_manager import MemoryManager  # type: ignore
    from structured_memory import StructuredMemory  # type: ignore
    from vector_store import VectorStore  # type: ignore

    persist_dir = _persist_dir()
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


def main():
    mm = _build_mm()
    token = os.getenv("TELEGRAM_TOKEN") or ""
    user = os.getenv("ESTER_DEFAULT_USER", "Owner")
    d = MorningDigestDaemon(mm, providers=None, tg_token=token, default_user=user)
    res = d._tick()
    print(json.dumps({"ok": True, "result": res}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()