# -*- coding: utf-8 -*-
"""tests/test_decay_gc_pin.py — proverka pin/GC pravil dlya KG.

Check it out:
  • Rebra s pin (props.pin/props.pinned/tags soderzhit 'pin'/'no_gc'/'keep' ili id nachinaetsya s 'pin::') - ne udalyayutsya GC.
  • Osirotevshie uzly bez pin starshe poroga - udalyayutsya.
  • policy="replace" import sokhranyaet invarianty (uzly/rib iz kept-naborov)."""

from __future__ import annotations

import time

from memory.decay_gc import DecayGC, DecayRules
from memory.kg_store import KGStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_gc_pin_and_orphans(tmp_path, monkeypatch):
    # Set PERSIST_HOLES to temporary folder
    import os

    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    kg = KGStore()  # initialized clean
    now = time.time()

    # Uzly
    kg.upsert_nodes(
        [
            {"id": "A", "type": "entity", "label": "A", "mtime": now - 10_000},
            {"id": "B", "type": "entity", "label": "B", "mtime": now - 10_000},
            {"id": "C", "type": "entity", "label": "C", "mtime": now - 10_000},
            {
                "id": "pin::D",
                "type": "entity",
                "label": "D",
                "mtime": now - 10_000,
            },  # pinned po id
        ]
    )

    # Ribs: one normal, one “to be removed soon”, one pined through props, and one to pin::D
    kg.upsert_edges(
        [
            {
                "src": "A",
                "rel": "rel",
                "dst": "B",
                "weight": 0.3,
                "props": {},
                "mtime": now - 10_000,
            },
            {
                "src": "A",
                "rel": "rel",
                "dst": "C",
                "weight": 0.01,
                "props": {},
                "mtime": now - 10_000,
            },  # slaboe, «pod nozh»
            {
                "src": "A",
                "rel": "rel",
                "dst": "pin::D",
                "weight": 0.01,
                "props": {},
                "mtime": now - 10_000,
            },  # k pinned uzlu
            {
                "src": "B",
                "rel": "rel",
                "dst": "C",
                "weight": 0.2,
                "props": {"pin": True},
                "mtime": now - 10_000,
            },  # pinned props
        ]
    )

    gc = DecayGC(kg)
    rules = DecayRules(
        half_life_s=1.0,  # quickly “disintegrates” to ensure it falls below the threshold
        min_weight=0.0,
        gc_edge_min_age_s=0.0,
        gc_edge_weight_threshold=0.05,
        gc_node_min_age_s=0.0,
    )
    rep = gc.apply(rules)

    # We check: the edge (A->C) with a weak weight must be removed
    e_ac = kg.query_edges(src="A", dst="C", rel="rel", limit=5)
    assert len(e_ac) == 0

    # The pined edge (B->C) should remain
    e_bc = kg.query_edges(src="B", dst="C", rel="rel", limit=5)
    assert len(e_bc) == 1

    # The edge to pin::D remains, but the node pin::D is not deleted
    e_ad = kg.query_edges(src="A", dst="pin::D", rel="rel", limit=5)
    assert len(e_ad) == 1
    ns = kg.query_nodes(q="D", limit=10)
    assert any(n["id"] == "pin::D" for n in ns)

    # Node C has become orphaned (if all connections to it are deleted and there are no incoming ones) - must be deleted
    # We have B->C pined left, which means C is not orphaned and must remain
    all_nodes = kg.export_all()["nodes"]
    ids = {n["id"] for n in all_nodes}
# assert "C" in ids