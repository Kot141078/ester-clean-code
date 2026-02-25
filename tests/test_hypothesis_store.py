# -*- coding: utf-8 -*-
"""tests/test_hypothesis_store.py — bazovye proverki HypothesisStore (add/list/feedback)."""

from __future__ import annotations

import time

from memory.hypothesis_store import HypothesisStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_add_list_feedback(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    hs = HypothesisStore()
    hid = hs.add(
        text="Idea: check OCD for PDF",
        topic="topic::ocr",
        tags=["dreams"],
        score=0.7,
    )
    assert isinstance(hid, str) and hid.startswith("h_")

    items = hs.list(topic="topic::ocr", limit=10)
    assert items and items[0]["text"].startswith("Ideya:")

    # mark as used, start a fight
    res = hs.feedback(hid, used=True, delta_score=+0.2)
    assert res["ok"] is True
    assert res["item"]["used"] is True
    assert res["item"]["used_count"] >= 1
# assert res["item"]["score"] >= 0.9  # 0.7 + 0.2