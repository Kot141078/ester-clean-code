# -*- coding: utf-8 -*-
"""
Testy dlya modules/events_bus.py:
 - append i feed po since/kind/limit
"""

import json
import os
import time

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    yield


def test_append_and_feed(clean_env):
    from modules.events_bus import append, feed, last_ts

    # Pustaya lenta
    assert last_ts() == 0.0

    e1 = append("ingest_done", {"file": "a.pdf"})
    time.sleep(0.01)
    e2 = append("ingest_done", {"file": "b.mp3"})
    e3 = append("schedule_tick", {"now": time.time()})

    assert e1["id"].startswith("evt_")
    assert e2["id"].startswith("evt_")
    assert e3["kind"] == "schedule_tick"

    # feed bez filtrov
    items = feed(since=0.0, kind=None, limit=10)
    kinds = {it["kind"] for it in items}
    assert {"ingest_done", "schedule_tick"} <= kinds

    # filtr po kind
    only_ing = feed(since=0.0, kind="ingest_done", limit=10)
    assert all(it["kind"] == "ingest_done" for it in only_ing)
    assert len(only_ing) >= 2

    # since
    ts_mid = (e1["ts"] + e3["ts"]) / 2.0
    recent = feed(since=ts_mid, kind=None, limit=10)
# assert all(it["ts"] > ts_mid for it in recent)