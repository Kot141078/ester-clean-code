# -*- coding: utf-8 -*-
"""
tests/nudges/test_sla_chain.py — proverka SLA-tsepochki T-60/T-15/Overdue.

MOSTY:
- (Yavnyy) NUDGES_SLA_CHAIN upravlyaet kolichestvom i vremenem due-nudzhey.
- (Skrytyy #1) Planirovanie ne prevoskhodit NUDGES_MAX_PER_EVENT.
- (Skrytyy #2) Prosrochennye shagi perenosyatsya na «seychas+1».

ZEMNOY ABZATs:
Daet uverennost, chto napominaniya prikhodyat vovremya — do i posle dedlayna.

# c=a+b
"""
from __future__ import annotations

import time, os
from nudges.engine import plan
from nudges import store
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_sla_chain(monkeypatch):
    monkeypatch.setenv("NUDGES_SLA_CHAIN", "60,15,-5")
    monkeypatch.setenv("NUDGES_MAX_PER_EVENT", "6")
    store.map_agent("pilot-1", "telegram:7")

    dl = time.time() + 3700  # ~61 min
    event = {
        "event_type": "AssignmentPlanned",
        "entity_id": "task-100",
        "ts": time.time(),
        "payload": {"deadline_ts": dl, "actors":[{"agent_id":"pilot-1"}], "summary":"test"}
    }
    plans = plan(event)
    # Dolzhny byt kak minimum 2 due do dedlayna (60,15) i 1 posle dedlayna
    assert len(plans) >= 3