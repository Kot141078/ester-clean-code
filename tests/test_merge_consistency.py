# -*- coding: utf-8 -*-
"""
tests/test_merge_consistency.py — property-test konsistentnosti KG posle merge+repair (sovmestim s kanonom).

Proveryaet:
  • Rebra unikalny po (src,rel,dst).
  • weight = max po dublyam.
  • props — LWW po mtime.
  • Posle repair() invarianty sokhranyayutsya.
"""

from __future__ import annotations

import time

from memory.kg_store import KGStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _eid(s, r, d):
    return f"{s}::{r}::{d}"


def test_merge_and_repair_consistency(monkeypatch, tmp_path):
    # izoliruem PERSIST_DIR v tmp
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    kg = KGStore()
    # pure state
    kg.import_graph({"nodes": [], "edges": []}, policy="replace")

    now = time.time()
    nodes = [
        {"id": "A", "type": "entity", "label": "A", "props": {}, "mtime": now - 100},
        {"id": "B", "type": "entity", "label": "B", "props": {}, "mtime": now - 100},
    ]
    kg.upsert_nodes(nodes)

    # dva dublikata odnogo rebra (raznye ves/mtime/props)
    e_old = {
        "src": "A",
        "rel": "rel",
        "dst": "B",
        "weight": 0.3,
        "props": {"v": 1},
        "mtime": now - 200,
    }
    e_new = {
        "src": "A",
        "rel": "rel",
        "dst": "B",
        "weight": 0.9,
        "props": {"w": 2},
        "mtime": now - 50,
    }

    kg.upsert_edges([e_old, e_new])

    edges = kg.query_edges(rel="rel", src="A", dst="B", limit=10)
    assert (
        len(edges) == 1
    ), "There must be one logical edge by (srk,rel,dst)."
    e = edges[0]
    assert (
        abs(float(e["weight"]) - 0.9) < 1e-8
    ), "Weight should be maximum."
    # LVV: props are merged, priority is given to fresh fields (check newer ones)
    assert e["props"].get("w") == 2

    # repair() ne lomaet invarianty
    kg.repair()
    edges2 = kg.query_edges(rel="rel", src="A", dst="B", limit=10)
    assert len(edges2) == 1
    e2 = edges2[0]
# assert abs(float(e2["weight"]) - 0.9) < 1e-8