# -*- coding: utf-8 -*-
from __future__ import annotations

from memory.hypothesis_store import HypothesisStore


def test_hypothesis_store_compat_crud(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    store = HypothesisStore()
    hid = store.add("Gipoteza o CRDT", topic="replication", tags=["dream"], score=0.5)
    assert hid.startswith("h_")

    same = store.add("Gipoteza o CRDT", topic="replication", tags=["mesh"], score=0.7)
    assert same == hid

    item = store.get(hid)
    assert item is not None
    assert item["score"] == 0.7
    assert set(item["tags"]) == {"dream", "mesh"}

    listed = store.list(topic="replication", limit=10)
    assert [row["id"] for row in listed] == [hid]

    feedback = store.feedback(hid, used=True, delta_score=0.2)
    assert feedback["ok"] is True
    assert feedback["item"]["used"] is True
    assert feedback["item"]["used_count"] == 1

    reloaded = HypothesisStore()
    assert reloaded.get(hid) is not None
    assert reloaded.delete(hid) is True
    assert reloaded.get(hid) is None
