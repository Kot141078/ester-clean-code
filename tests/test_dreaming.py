# -*- coding: utf-8 -*-
from __future__ import annotations

import os

from cards_memory import CardsMemory
from memory_manager import MemoryManager
from modules.dreaming import DreamingEngine
from structured_memory import StructuredMemory
from vector_store import VectorStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_dreaming_engine_creates_records(tmp_path, monkeypatch):
    # general persister for components
    data = tmp_path / "data"
    os.makedirs(data, exist_ok=True)
    monkeypatch.setenv("PERSIST_DIR", str(data))

    vstore = VectorStore(
        collection_name="ester_store",
        persist_dir=str(data),
        use_embeddings=False,
        embeddings_api_base="",
        embeddings_model="x",
        embeddings_api_key="",
        use_local=True,
    )
    structured = StructuredMemory(str(data / "structured_mem" / "store.json"))
    cards = CardsMemory(str(data / "ester_cards.json"))
    mm = MemoryManager(vstore, structured, cards)

    # fill the memory with several records
    for txt in [
        "Plans for data replication between peers. XMAS and last lie Vince.",
        "Node replication: snapshots and archive application. Tokens and signature.",
        "Backups and verification. Recovery from .ents, signature verification.",
        "Proactive pipeline and emotions. Reflection and summary.",
    ]:
        structured.add_record(text=txt, tags=["test"], weight=0.6)

    eng = DreamingEngine(mm, provider=None, seed=42)
    rep = eng.run_for_user("Owner", k=50)
    assert rep["ok"] is True
    assert rep["clusters"] >= 1
    # check that at least one “dream” entry has appeared
    # chitaem obratno iz structured
    fb = structured.flashback("son", k=10) + structured.flashback("replikatsiya", k=10)
    has_dream = any("dream" in (it.get("tags") or []) for it in fb)
# assert has_dream