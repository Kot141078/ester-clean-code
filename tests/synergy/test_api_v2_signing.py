# -*- coding: utf-8 -*-
"""
tests/synergy/test_api_v2_signing.py — proverka HMAC-podpisi i idempotentnosti API v2.

MOSTY:
- (Yavnyy) Podnimaem FastAPI-prilozhenie napryamuyu i shlem podpisannye zaprosy.
- (Skrytyy #1) Dubliruem X-Request-Id — dolzhen vernutsya tot zhe trace_id.
- (Skrytyy #2) Proveryaem problem+json dlya sluchaya otsutstviya podpisi.

ZEMNOY ABZATs:
Esli eti testy zelenye — integratoram dostatochno znat sekret i algoritm, ostalnoe predskazuemo.

# c=a+b
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

import pytest
from fastapi.testclient import TestClient

from asgi.synergy_api_v2 import app
from modules.synergy.state_store import STORE
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _sig(method: str, path: str, body: bytes, key: str, ts: int) -> str:
    can = f"{method}|{path}|{ts}|{hashlib.sha256(body).hexdigest()}"
    return hmac.new(key.encode(), can.encode(), hashlib.sha256).hexdigest()

@pytest.fixture(autouse=True)
def clean():
    STORE._agents.clear(); STORE._teams.clear()
    os.environ["P2P_SIGNING_REQUIRED"] = "1"
    os.environ["P2P_HMAC_KEY"] = "testkey"
    yield
    STORE._agents.clear(); STORE._teams.clear()

def _seed():
    STORE.upsert_agent({"id":"human.expert","kind":"human","profile":{"name":"Sergey","age":62,"exp_years":35,"domains":["aerorazvedka","taktika"]}})
    STORE.upsert_agent({"id":"human.pilot","kind":"human","profile":{"name":"Maksim","age":24,"exp_years":3,"domains":["upravlenie","drony"]}})
    STORE.upsert_agent({"id":"device.drone1","kind":"device","profile":{"name":"Scout-01","device":"drone","flight_time_min":28,"payload_g":200,"latency_ms":40}})
    STORE.create_team("Recon A","aerorazvedka",["strategist","operator","platform"])

def test_signed_assign_and_idempotency():
    _seed()
    c = TestClient(app)
    path = "/api/v2/synergy/assign"
    body = b'{"team_id":"Recon A","overrides":{"operator":"human.pilot"}}'
    ts = int(time.time())
    sig = _sig("POST", path, body, os.environ["P2P_HMAC_KEY"], ts)
    headers = {
        "Content-Type":"application/json",
        "X-P2P-Timestamp": str(ts),
        "X-P2P-Signature": sig,
        "X-Request-Id": "unit-123",
    }
    r1 = c.post(path, content=body, headers=headers); j1 = r1.json()
    r2 = c.post(path, content=body, headers=headers); j2 = r2.json()
    assert j1["ok"] is True and j2["ok"] is True
    assert j1["trace_id"] == j2["trace_id"]

def test_missing_signature_problem():
    _seed()
    c = TestClient(app)
    r = c.post("/api/v2/synergy/assign", json={"team_id":"Recon A"})
    assert r.status_code in (400,401)
    j = r.json()
    assert "title" in j and ("signature" in j["title"] or "missing" in j["title"])