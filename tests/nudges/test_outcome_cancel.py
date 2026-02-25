# -*- coding: utf-8 -*-
"""tests/nudges/test_outcome_cancel.py — Outcome gasit pending by entity_id.

MOSTY:
- (Yavnyy) skip_pending_by_entity pomechaet new → skipped:outcome.
- (Skrytyy #1) /nudges/event reagiruet na OutcomeReported do postanovki novykh nudzhey.
- (Skrytyy #2) Metriki otrazhayut zakrytiya.

ZEMNOY ABZATs:
Pokryvaem avtomaticheskoe snyatie “dozhimalok”, kogda zadacha zakrylas.

# c=a+b"""
from __future__ import annotations

import time, os

from nudges import store
from nudges.engine import plan
from routes.nudges_routes import nudges_event
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

async def test_outcome_cancels_pending(monkeypatch, anyio_backend):
    monkeypatch.setenv("MESSAGING_DB_PATH", "data/test_nudges_outcome.sqlite")
    store.map_agent("x", "telegram:1")

    # Let's create an event with a deadline (put it in the event/queue manually)
    ev_id = store.add_event("AssignmentPlanned", "task-X", time.time(), {"deadline_ts": time.time()+60, "actors":[{"agent_id":"x"}], "summary":"X"})
    ev = store.read_event(ev_id)
    for p in plan(ev):
        store.enqueue(ev_id, p["due_ts"], p["key"], p["kind"], p["intent"])

    # OutcomeReported po toy zhe entity_id
    payload = {"event_type":"OutcomeReported","entity_id":"task-X","ts":time.time(),"payload":{"actors":[{"agent_id":"x"}],"summary":"X","outcome":"ok"}}
    # dergaem endpoint napryamuyu
    res = await nudges_event(payload)
    assert res.status_code == 200

    # All Pending on Task-Ks must stop being boring
    pend = store.list_pending(limit=100, due_only=False)
    assert all(p[7] != 'new' for p in pend)
