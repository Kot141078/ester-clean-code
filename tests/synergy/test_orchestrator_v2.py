# -*- coding: utf-8 -*-
"""
tests/synergy/test_orchestrator_v2.py — dymovye testy prodvinutogo orkestratora v2.

MOSTY:
- (Yavnyy) Proveryaem vybor luchshey platformy, uvazhenie overraydov i idempotentnost po request_id.
- (Skrytyy #1) Ubezhdaemsya, chto platform ne naznachaetsya cheloveku (HARD-konstreynt).
- (Skrytyy #2) Trace soderzhit nachalnyy shag i (vozmozhnye) svapy.

ZEMNOY ABZATs:
Pokryvaem klyuchevye svoystva: kachestvo vybora, predskazuemost i povtoryaemost.
Esli eti testy zelenye, orkestrator gotov k API-sloyu.

# c=a+b
"""
from __future__ import annotations
from flask import Flask
import pytest

from modules.synergy.state_store import STORE
from modules.synergy.orchestrator_v2 import assign_v2
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@pytest.fixture(autouse=True)
def clean_store():
    # Zhestkaya ochistka in-memory STORE
    STORE._agents.clear()
    STORE._teams.clear()
    yield
    STORE._agents.clear()
    STORE._teams.clear()

def _seed():
    # Lyudi
    STORE.upsert_agent({
        "id":"human.expert","kind":"human",
        "profile":{"name":"Sergey","age":62,"exp_years":35,"domains":["aerorazvedka","taktika"]},
        "bio":"veteran, strateg"
    })
    STORE.upsert_agent({
        "id":"human.pilot","kind":"human",
        "profile":{"name":"Maksim","age":24,"exp_years":3,"domains":["upravlenie","drony"]},
        "bio":"bystrye reaktsii"
    })
    # Platformy
    STORE.upsert_agent({
        "id":"device.drone_fast","kind":"device",
        "profile":{"name":"Scout-F","device":"drone","flight_time_min":28,"payload_g":200,"latency_ms":40}
    })
    STORE.upsert_agent({
        "id":"device.drone_slow","kind":"device",
        "profile":{"name":"Scout-S","device":"drone","flight_time_min":10,"payload_g":500,"latency_ms":600}
    })
    # Komanda
    STORE.create_team("Recon T","aerorazvedka",["strategist","operator","platform"])

def test_assign_respects_overrides_and_picks_best_platform():
    _seed()
    res = assign_v2("Recon T", overrides={"operator":"human.pilot"}, request_id="RID-1")
    assert res["ok"] is True
    a = res["assigned"]
    assert a["operator"] == "human.pilot"
    assert a["strategist"] == "human.expert"
    # Luchshaya platforma — nizkaya latency i prilichnoe vremya
    assert a["platform"] == "device.drone_fast"
    # HARD: platforma ne dolzhna byt chelovekom
    assert a["platform"].startswith("device.")

def test_idempotency_same_request_id_same_trace():
    _seed()
    r1 = assign_v2("Recon T", overrides={"operator":"human.pilot"}, request_id="RID-XYZ")
    r2 = assign_v2("Recon T", overrides={"operator":"human.pilot"}, request_id="RID-XYZ")
    assert r1["assigned"] == r2["assigned"]
    assert r1["trace_id"] == r2["trace_id"]

def test_trace_and_penalties_exist():
    _seed()
    r = assign_v2("Recon T", overrides={}, request_id="RID-3")
    assert isinstance(r.get("steps"), list) and len(r["steps"]) >= 1
    assert "total" in r and "penalty" in r