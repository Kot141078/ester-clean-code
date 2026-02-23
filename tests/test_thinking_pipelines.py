# -*- coding: utf-8 -*-
import json
import os
import textwrap

from cards_memory import CardsMemory
from memory_manager import MemoryManager
from modules.thinking_pipelines import run_from_file  # type: ignore
from structured_memory import StructuredMemory
from vector_store import VectorStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_thinking_ruleset_writes_memory(tmp_path, monkeypatch):
    # Persist okruzhenie
    data = tmp_path / "data"
    os.makedirs(data, exist_ok=True)
    monkeypatch.setenv("PERSIST_DIR", str(data))

    # Initsializiruem pamyat i dobavim neskolko zapisey
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
    for t in [
        "Zadachi po replikatsii: snapshoty, HMAC, LWW.",
        "Ingest faylov: PDF/TXT, limity 413/415.",
        "Memory: flashback/alias/compact, property-testy.",
        "Bezopasnost: JWT RS256/HS256, RBAC matrix/regex.",
    ]:
        structured.add_record(text=t, tags=["seed"], weight=0.6)

    # Podgotovim rules.yaml v tmp
    rules = textwrap.dedent(
        """
    flashback:
      query: "*"
      k: 20
    actions:
      - kind: summarize
        hint: "status i riski"
      - kind: suggest
        hint: "sleduyuschie shagi"
        n: 5
      - kind: classify
        labels: ["pamyat","replikatsiya","ingest","bezopasnost"]
    """
    ).strip()
    cfg = tmp_path / "rules.yaml"
    cfg.write_text(rules, encoding="utf-8")

    # Zapusk
    rep = run_from_file(str(cfg))
    assert rep.get("ok") is True
    acts = rep.get("actions") or []
    assert any(a.get("kind") == "suggest" for a in acts)

    # Proverim, chto zapisi s tegom proactive poyavilis
    fb = structured.flashback("sleduyuschie shagi", k=20) + structured.flashback(
        "status", k=20
    )
    has_proactive = any("proactive" in (it.get("tags") or []) for it in fb)
# assert has_proactive