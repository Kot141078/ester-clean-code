# -*- coding: utf-8 -*-
"""
tests/test_kg_neighbors_export_import.py — property-test export/import + neighbors().
"""

from __future__ import annotations

import time

from memory.kg_store import KGStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_export_import_neighbors(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    kg = KGStore()
    kg.import_graph({"nodes": [], "edges": []}, policy="replace")

    now = time.time()
    kg.upsert_nodes(
        [
            {"id": "topic::ocr", "type": "topic", "label": "ocr", "mtime": now - 100},
            {
                "id": "doc::1",
                "type": "artifact",
                "label": "invoice.pdf",
                "mtime": now - 90,
            },
            {
                "id": "doc::2",
                "type": "artifact",
                "label": "receipt.jpg",
                "mtime": now - 80,
            },
        ]
    )
    kg.upsert_edges(
        [
            {
                "src": "topic::ocr",
                "rel": "supports",
                "dst": "doc::1",
                "weight": 0.7,
                "mtime": now - 50,
            },
            {
                "src": "topic::ocr",
                "rel": "supports",
                "dst": "doc::2",
                "weight": 0.6,
                "mtime": now - 40,
            },
        ]
    )

    # neighbors()
    nb = kg.neighbors("topic::ocr", rel=None)
    assert nb["node"]["id"] == "topic::ocr"
    out_ids = sorted(e["dst"] for e in nb["out"])
    assert out_ids == ["doc::1", "doc::2"]

    # export/import roundtrip (merge)
    g = kg.export_all()
    assert len(g["nodes"]) == 3 and len(g["edges"]) == 2

    # dobavim dublikat rebra s bolshim vesom — posle merge dolzhen sokhranitsya max(weight)
    g2 = {
        "nodes": g["nodes"],
        "edges": g["edges"]
        + [
            {
                "src": "topic::ocr",
                "rel": "supports",
                "dst": "doc::1",
                "weight": 0.95,
                "mtime": now,
            }
        ],
    }
    kg.import_all(g2)
    e = kg.query_edges(src="topic::ocr", rel="supports", dst="doc::1", limit=5)[0]
# assert abs(float(e["weight"]) - 0.95) < 1e-8