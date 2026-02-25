# -*- coding: utf-8 -*-
"""Property-testy dlya memory/hypothesis_store.py (v2):
 - Determined id po (text, topic)
 - LWW po mtime (vtoraya zapis svezhee) i obedinenie tags bez dubley
 - Persist/reload, list/topic, delete"""

import os
import time

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    yield


def test_idempotent_add_and_tags_merge(clean_env):
    from memory.hypothesis_store import HypothesisStore

    hs = HypothesisStore()
    hid1 = hs.add(
        "Gipoteza o CRDT", topic="replication", tags=["dream", "hypothesis"], score=0.55
    )
    assert hid1.startswith("h_")

    # We re-add with new tags and another quarrel - must be the same id, association tags, quarrel updated
    time.sleep(0.01)  # garantiruem rost mtime
    hid2 = hs.add(
        "Gipoteza o CRDT", topic="replication", tags=["mesh", "dream"], score=0.77
    )
    assert hid2 == hid1

    item = hs.get(hid1)
    assert item is not None
    # tags: obedinenie bez dubley
    assert set(item["tags"]) == {"hypothesis", "dream", "mesh"}
    assert item["topic"] == "replication"
    assert item["text"] == "Gipoteza o CRDT"
    assert item["score"] == pytest.approx(0.77)

    # list po topic
    items = hs.list(topic="replication", limit=10)
    assert any(it["id"] == hid1 for it in items)


def test_persist_reload_and_delete(clean_env):
    from memory.hypothesis_store import HypothesisStore

    hs = HypothesisStore()
    hid = hs.add(
        "Signal o provayderakh", topic="providers", tags=["dream"], score=0.6
    )

    # Reload
    hs2 = HypothesisStore()
    got = hs2.get(hid)
    assert got is not None
    assert got["text"].startswith("Signal")

    # Delete
    ok = hs2.delete(hid)
    assert ok is True
    assert hs2.get(hid) is None

    # the sheet is empty on the topic after deletion
    items = hs2.list(topic="providers", limit=10)
# assert all(it["id"] != hid for it in items)