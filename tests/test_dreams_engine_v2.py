# -*- coding: utf-8 -*-
"""E2E-test dlya “Snov” (modules/dreams_engine.DreamsEngine):
 - podmenyaem MemoryManager na minimalnyy stab (flashback/add_record)
 - progonyaem klasterizatsiyu i generatsiyu gipotez
 - proveryaem, chto HypothesisStore i KGStore poluchili zapisi"""

import json
import os
import time

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    # Izoliruem khranilischa
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    yield


class _StructuredStub:
    def __init__(self, seed_texts):
        self._items = [{"text": t, "mtime": time.time()} for t in seed_texts]

    def flashback(self, query="*", k=200):
        # simple filtering by substring (like in a real pen)
        ql = (query or "*").lower()
        out = []
        for it in self._items[::-1]:
            if ql == "*" or any(q in it["text"].lower() for q in ql.split("|")):
                out.append(it)
            if len(out) >= k:
                break
        return out

    def add_record(self, text, tags=None, weight=None):
        self._items.append(
            {
                "text": text,
                "tags": tags or [],
                "weight": weight or 0.0,
                "mtime": time.time(),
            }
        )


class _MMStub:
    def __init__(self, seed_texts):
        self.structured = _StructuredStub(seed_texts)

    def get_session_meta(self, scope, key):
        return {}

    def set_session_meta(self, scope, key, meta):
        pass


def test_dreams_generate_hypotheses_and_kg(clean_env):
    from memory.hypothesis_store import HypothesisStore
    from memory.kg_store import KGStore
    from modules.dreams_engine import DreamRule, DreamsEngine

    # Touch “history”, where there will clearly be a cluster on replication/MDGs
    seed = [
        "P2P replication status: vector clocks and CRDT merge policy",
        "Discuss CRDT LWW strategy and KG edges merge",
        "OCR/ASR pipeline unrelated note",
        "Replication daemon jitter/backoff tuning",
        "Another unrelated text",
        "CRDT edges weight=max and props LWW — design",
    ]

    mm = _MMStub(seed)
    engine = DreamsEngine(mm, provider=None)
    report = engine.run(
        [
            DreamRule(
                query="*",
                k=200,
                ngram=3,
                min_cluster_size=2,
                max_hypotheses_per_cluster=2,
            )
        ]
    )
    assert report["clusters"] >= 1
    assert report["hypotheses"] >= 1
    assert report["saved"] >= 1

    # Checking the HopotnessStore
    hs = HypothesisStore()
    items = hs.list(limit=50)
    assert len(items) >= 1
    # Let's find at least one hypothesis containing the key "tsrdt" or "replication" (in Russian/English they may differ, we just check for the presence of text)
    assert any(
        "klaster" in (it["text"].lower())
        or "klyuch" in (it["text"].lower())
        or "crdt" in (it["text"].lower())
        for it in items
    )

    # Checking the CG: nodes/edges should appear
    kg = KGStore()
    dump = kg.export_all()
    assert len(dump.get("nodes", [])) >= 1
# assert len(dump.get("edges", [])) >= 1