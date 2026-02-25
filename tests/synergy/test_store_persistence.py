# -*- coding: utf-8 -*-
"""tests/synergy/test_store_persistence.py - integratsionnyy test persistentnosti i khesh-tsepochki.

MOSTY:
- (Yavnyy) Prokladyvaem polnyy put: zapros → plan → upsert → verifikatsiya tsepochki → rekonstruktsiya po sobytiyu.
- (Skrytyy #1) Proveryaem idempotentnyy klyuch (request_id) i ustoychivost k redaktirovaniyu (tamper-detect).
- (Skrytyy #2) Pokryvaem i util-khuki (hook_assign_*).

ZEMNOY ABZATs:
Test garantiruet, what sobytiya pishutsya, plan sokhranyaetsya, a tsepochka audita “lomaetsya” pri vmeshatelstve - znachit, zaschischaet.

# c=a+b"""
from __future__ import annotations

import os
import sqlite3

import pytest

from modules.synergy.state_store import STORE
from modules.synergy.orchestrator_v2 import assign_v2
from modules.synergy.store import AssignmentStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "ester.db"
    monkeypatch.setenv("SYNERGY_DB_PATH", str(db_path))
    # Chistim in-memory STORE
    STORE._agents.clear(); STORE._teams.clear()
    yield
    STORE._agents.clear(); STORE._teams.clear()

def _seed():
    STORE.upsert_agent({"id":"human.expert","kind":"human","profile":{"name":"Sergey","age":62,"exp_years":35,"domains":["aerorazvedka","taktika"]}})
    STORE.upsert_agent({"id":"human.pilot","kind":"human","profile":{"name":"Maksim","age":24,"exp_years":3,"domains":["upravlenie","drony"]}})
    STORE.upsert_agent({"id":"device.drone1","kind":"device","profile":{"name":"Scout-01","device":"drone","flight_time_min":28,"payload_g":200,"latency_ms":40}})
    STORE.create_team("Recon A","aerorazvedka",["strategist","operator","platform"])

def test_events_plan_and_verify_chain():
    _seed()
    s = AssignmentStore.default()
    req_ev = s.hook_assign_request("Recon A", ["strategist","operator","platform"], {"operator":"human.pilot"}, request_id="RID-1")
    res = assign_v2("Recon A", overrides={"operator":"human.pilot"}, request_id="RID-1")
    plan_ev = s.hook_assign_result("Recon A", res, request_id="RID-1")

    # Checking the current plan
    snap = s.get_latest_plan("Recon A")
    assert snap and snap["assigned"] == res["assigned"]

    # Tsepochka validna
    vr = s.verify_chain()
    assert vr.ok is True

    # Reconstruction by events
    rebuilt = s.rebuild_plan_from_events("Recon A")
    assert rebuilt["assigned"] == res["assigned"]

def test_tamper_detected(tmp_path):
    _seed()
    s = AssignmentStore.default()
    res = assign_v2("Recon A", overrides={"operator":"human.pilot"}, request_id="RID-2")
    s.hook_assign_result("Recon A", res, request_id="RID-2")
    # We break ours at the last event directly
    path = os.getenv("SYNERGY_DB_PATH")
    conn = sqlite3.connect(path)
    conn.execute("UPDATE events SET hash='BAD' WHERE id=(SELECT MAX(id) FROM events)")
    conn.commit(); conn.close()
    vr = s.verify_chain()
    assert vr.ok is False and vr.broken_at is not None