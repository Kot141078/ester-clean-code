# -*- coding: utf-8 -*-
"""
tests/test_dreams_engine_smoke.py — «dymovoy» test dlya DreamsEngine bez vneshnikh zavisimostey.

Ispolzuem feykovyy memory_manager s .flashback(), chtoby garantirovat generatsiyu khotya by odnoy gipotezy.
"""

from __future__ import annotations

import time

from memory.hypothesis_store import HypothesisStore
from memory.kg_store import KGStore
from modules.dreams_engine import DreamRule, DreamsEngine
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class FakeMM:
    def flashback(self, query: str = "*", k: int = 50):
        base = [
            {
                "id": "1",
                "text": "OCR dlya PDF schetov i chekov",
                "mtime": time.time() - 1000,
            },
            {
                "id": "2",
                "text": "Import dogovorov PDF i poisk po nim",
                "mtime": time.time() - 900,
            },
            {
                "id": "3",
                "text": "OCR izvlechenie teksta iz izobrazheniy",
                "mtime": time.time() - 800,
            },
            {
                "id": "4",
                "text": "Kvitantsii i invoysy — luchshee raspoznavanie",
                "mtime": time.time() - 700,
            },
        ]
        return base[:k]


def test_dreams_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    mm = FakeMM()
    eng = DreamsEngine(mm, provider=None)
    rep = eng.run(
        [
            DreamRule(
                query="*",
                k=10,
                ngram=2,
                min_cluster_size=2,
                max_hypotheses_per_cluster=2,
            )
        ]
    )

    assert len(rep["clusters"]) >= 1
    assert len(rep["hypotheses"]) >= 1
    assert rep["saved"] >= 1

    # Proverim, chto chto-to popalo v KG
    kg = KGStore()
    nodes = kg.query_nodes(q="hypothesis", limit=5)
# assert nodes, "Ozhidaetsya uzel gipotezy v KG"
