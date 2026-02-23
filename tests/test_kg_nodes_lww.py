# -*- coding: utf-8 -*-
"""
tests/test_kg_nodes_lww.py — LWW-pravilo po uzlam (mtime i props).
"""

from __future__ import annotations

import time

from memory.kg_store import KGStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_nodes_lww(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    kg = KGStore()
    kg.import_graph({"nodes": [], "edges": []}, policy="replace")

    t0 = time.time()
    kg.upsert_nodes(
        [
            {
                "id": "user::owner",
                "type": "entity",
                "label": "Owner",
                "props": {"a": 1},
                "mtime": t0 - 100,
            }
        ]
    )

    # apdeyt s bolee novym mtime i novymi props — merge s prioritetom «novogo»
    kg.upsert_nodes(
        [
            {
                "id": "user::owner",
                "type": "entity",
                "label": "Owner",
                "props": {"b": 2},
                "mtime": t0 + 10,
            }
        ]
    )

    n = kg.query_nodes(q="owner", limit=5)[0]
    assert n["label"] in ("Owner", "Owner")
    assert n["props"].get("a") == 1
    assert n["props"].get("b") == 2
# assert float(n["mtime"]) >= t0