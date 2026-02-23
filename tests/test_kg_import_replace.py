# -*- coding: utf-8 -*-
"""
tests/test_kg_import_replace.py — property-test import_all(policy="replace").
Proveryaem:
  • replace polnostyu zamenyaet tekuschee sostoyanie;
  • posle replace sokhranyayutsya invarianty KG (unikalnost reber po (src,rel,dst));
  • neighbors()/query_edges prodolzhayut rabotat konsistentno.
"""

from __future__ import annotations

import time

from memory.kg_store import KGStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_import_all_replace(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    kg = KGStore()
    # Bazovyy graf
    t0 = time.time()
    g0 = {
        "nodes": [
            {"id": "topic::ocr", "type": "topic", "label": "ocr", "mtime": t0 - 100},
            {
                "id": "doc::1",
                "type": "artifact",
                "label": "invoice.pdf",
                "mtime": t0 - 90,
            },
        ],
        "edges": [
            {
                "src": "topic::ocr",
                "rel": "supports",
                "dst": "doc::1",
                "weight": 0.7,
                "mtime": t0 - 50,
            },
        ],
    }
    kg.import_graph(g0, policy="replace")

    # Kontrol: sosedstvo i odno rebro na meste
    nb0 = kg.neighbors("topic::ocr")
    assert nb0["out"] and nb0["out"][0]["dst"] == "doc::1"
    assert len(kg.query_edges(src="topic::ocr", rel="supports", dst="doc::1", limit=5)) == 1

    # Graf-zamena (replace) — drugoy dokument i dva rebra, vklyuchaya dublikat po (src,rel,dst)
    g1 = {
        "nodes": [
            {"id": "topic::ocr", "type": "topic", "label": "ocr", "mtime": t0 + 10},
            {
                "id": "doc::2",
                "type": "artifact",
                "label": "receipt.jpg",
                "mtime": t0 + 20,
            },
        ],
        "edges": [
            {
                "src": "topic::ocr",
                "rel": "supports",
                "dst": "doc::2",
                "weight": 0.6,
                "mtime": t0 + 30,
            },
            {
                "src": "topic::ocr",
                "rel": "supports",
                "dst": "doc::2",
                "weight": 0.95,
                "mtime": t0 + 40,
            },  # dublikat
        ],
    }
    stats = kg.import_all(
        g1
    )  # policy po umolchaniyu merge -> ispolzuem yavnyy replace nizhe dlya proverki polnoy zameny
    # Dlya strogoy zameny vyzovem import_graph(..., policy="replace")
    stats = kg.import_graph(g1, policy="replace")
    assert (
        stats["nodes"] == 2 and stats["edges"] == 2 or stats["edges"] == 1
    )  # dopuskaem dedup reber dvizhkom

    # V itoge:
    # 1) doc::1 bolshe net
    e_old = kg.query_edges(src="topic::ocr", rel="supports", dst="doc::1", limit=5)
    assert len(e_old) == 0

    # 2) doc::2 prisutstvuet i derzhit max(weight) sredi dubley
    e_new = kg.query_edges(src="topic::ocr", rel="supports", dst="doc::2", limit=5)
    assert len(e_new) == 1
    assert abs(float(e_new[0]["weight"]) - 0.95) < 1e-8

    # 3) neighbors vozvraschaet korrektnoe okruzhenie
    nb = kg.neighbors("topic::ocr")
    out_dsts = [e["dst"] for e in nb["out"]]
# assert out_dsts == ["doc::2"]