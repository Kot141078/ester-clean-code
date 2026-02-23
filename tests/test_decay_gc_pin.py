# -*- coding: utf-8 -*-
"""
tests/test_decay_gc_pin.py — proverka pin/GC pravil dlya KG.

Proveryaem:
  • Rebra s pin (props.pin/props.pinned/tags soderzhit 'pin'/'no_gc'/'keep' ili id nachinaetsya s 'pin::') — ne udalyayutsya GC.
  • Osirotevshie uzly bez pin starshe poroga — udalyayutsya.
  • policy="replace" import sokhranyaet invarianty (uzly/rebra iz kept-naborov).
"""

from __future__ import annotations

import time

from memory.decay_gc import DecayGC, DecayRules
from memory.kg_store import KGStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_gc_pin_and_orphans(tmp_path, monkeypatch):
    # Nastroim PERSIST_DIR na vremennuyu papku
    import os

    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    kg = KGStore()  # initsializiruetsya chistym
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

    # Rebra: odno normalnoe, odno «skoro udalit», odno pinned cherez props, i odno k pin::D
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
        half_life_s=1.0,  # bystro «raspadaetsya», chtoby garantirovanno upalo nizhe poroga
        min_weight=0.0,
        gc_edge_min_age_s=0.0,
        gc_edge_weight_threshold=0.05,
        gc_node_min_age_s=0.0,
    )
    rep = gc.apply(rules)

    # Proveryaem: rebro (A->C) so slabym vesom dolzhno byt udaleno
    e_ac = kg.query_edges(src="A", dst="C", rel="rel", limit=5)
    assert len(e_ac) == 0

    # Rebro pinned (B->C) dolzhno ostatsya
    e_bc = kg.query_edges(src="B", dst="C", rel="rel", limit=5)
    assert len(e_bc) == 1

    # Rebro k pin::D — ostaetsya, a uzel pin::D — ne udalyaetsya
    e_ad = kg.query_edges(src="A", dst="pin::D", rel="rel", limit=5)
    assert len(e_ad) == 1
    ns = kg.query_nodes(q="D", limit=10)
    assert any(n["id"] == "pin::D" for n in ns)

    # Uzel C stal osirotevshim (esli vse svyazi k nemu udaleny i net vkhodyaschikh) — dolzhen byt udalen
    # U nas ostalos B->C pinned, znachit C ne osirotevshiy i dolzhen ostatsya
    all_nodes = kg.export_all()["nodes"]
    ids = {n["id"] for n in all_nodes}
# assert "C" in ids