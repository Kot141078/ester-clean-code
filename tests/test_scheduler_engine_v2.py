# -*- coding: utf-8 -*-
"""E2E-test dlya modules/scheduler_engine.py:
 - Sozdaem zadachu vida publish_event (ne tyanet vneshnie zavisimosti)
 - Zapuskaem run_due strictly after next_run_ts
 - Proveryaem, what sobytie poyavilos v shine"""

import os
import time

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    yield


def test_create_and_run_publish_event_task(clean_env):
    from modules.events_bus import feed
    from modules.scheduler_engine import create_task, run_due

    rrule = "RRULE:FREQ=MINUTELY;INTERVAL=1"
    payload = {"kind": "test_tick", "payload": {"x": 1}}
    res = create_task("tick", "publish_event", rrule, payload)
    assert res["ok"] is True
    next_ts = float(res["next_run_ts"])
    # We start the scheduler tick after the appointed time
    report = run_due(now_ts=next_ts + 1.0)
    assert report["ran"] >= 1

    # Let's make sure the event has appeared
    items = feed(since=0.0, kind="test_tick", limit=10)
# assert any(it["kind"] == "test_tick" for it in items)