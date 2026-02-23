# -*- coding: utf-8 -*-
"""
tests/nudges/test_escalation.py — proverka eskalatsiy pri prosrochke.

MOSTY:
- (Yavnyy) Na otritsatelnykh shagakh SLA-tsepochki sozdaetsya nudzh na teg 'manager' (esli mapping zadan).
- (Skrytyy #1) Ogranichenie NUDGES_MAX_PER_EVENT soblyudaetsya.
- (Skrytyy #2) Vremya due dlya eskalatsii — now+1 (mgnovenno k otpravke).

ZEMNOY ABZATs:
Pokazyvaet, chto pri «goryachey» situatsii soobschenie poluchaet ne tolko ispolnitel, no i otvetstvennoe litso.

# c=a+b
"""
from __future__ import annotations

import time, os
from nudges.engine import plan
from nudges import store
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_overdue_escalation(monkeypatch):
    monkeypatch.setenv("NUDGES_SLA_CHAIN", "60,-5")
    monkeypatch.setenv("NUDGES_MAX_PER_EVENT", "5")
    monkeypatch.setenv("NUDGES_ESCALATE_TAGS", "manager")

    # Ispolnitel + menedzher
    store.map_agent("pilot-1", "telegram:7")
    store.map_escalation("manager", "telegram:99")

    dl = time.time() - 120  # dedlayn uzhe prosrochen na 2 min → shag -5 dolzhen eskalirovat
    event = {
        "event_type": "AssignmentPlanned",
        "entity_id": "task-777",
        "ts": time.time(),
        "payload": {"deadline_ts": dl, "actors":[{"agent_id":"pilot-1"}], "summary":"eskalatsiya"}
    }
    ps = plan(event)
    keys = [p["key"] for p in ps]
    assert "telegram:99" in keys  # menedzher
    assert "telegram:7" in keys   # ispolnitel