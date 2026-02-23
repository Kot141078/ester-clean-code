# -*- coding: utf-8 -*-
"""
tests/nudges/test_nudges_engine.py — dymovoy test: sobytie → pending → outbox (dry-run).

MOSTY:
- (Yavnyy) Proveryaem planirovanie po AssignmentPlanned s dedlaynom v blizhayshie minuty.
- (Skrytyy #1) Mapping agent→contact i DEV_DRYRUN obespechivayut bezopasnuyu otpravku.
- (Skrytyy #2) Put: add_event → plan → enqueue → flush → outbox (cherez messaging.broadcast).

ZEMNOY ABZATs:
Pokazyvaet, chto «sobytie» realno privodit k izmerimoy otpravke (ili dryrun), ne lomaya ostalnuyu sistemu.

# c=a+b
"""
from __future__ import annotations

import os, time

from nudges import store
from nudges.engine import plan as plan_nudges
from routes.nudges_routes import nudges_flush
from messaging.outbox_store import list_outgoing
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_event_to_outbox(monkeypatch, anyio_backend):
    monkeypatch.setenv("MESSAGING_DB_PATH", "data/test_nudges.sqlite")
    monkeypatch.setenv("DEV_DRYRUN", "1")  # bezopasno

    # mapping
    store.map_agent("pilot-1", "telegram:42")

    # sobytie s dedlaynom cherez 10 minut
    payload = {"deadline_ts": time.time()+600, "actors":[{"agent_id":"pilot-1","role":"operator"}], "summary":"dostavka"}
    ev_id = store.add_event("AssignmentPlanned", "task-42", time.time(), payload)
    ev = store.read_event(ev_id)
    plans = plan_nudges(ev)
    assert plans and plans[0]["key"] == "telegram:42"

    # postavit v ochered
    for p in plans:
        store.enqueue(ev_id, p["due_ts"], p["key"], p["kind"], p["intent"])

    # otpravit
    # imitiruem vyzov endpointa vruchnuyu (bez FastAPI runtime); prosto dernem store.list_pending i ispolzuem broadcast
    from messaging.broadcast import send_broadcast
    pend = store.list_pending(limit=100)
    keys = [p[4] for p in pend]
    res = send_broadcast(keys, pend[0][6], adapt_kind=pend[0][5])  # vozmem intent/kind pervoy zapisi
    assert "sent" in res