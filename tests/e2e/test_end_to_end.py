# -*- coding: utf-8 -*-
"""
tests/e2e/test_end_to_end.py — skvoznoy test API v2: podpis, idempotentnost, obnovlenie bordy.

MOSTY:
- (Yavnyy) Podnimaem FastAPI-prilozhenie (asgi.synergy_api_v2.app), shlem podpisannye zaprosy na /api/v2/synergy/assign.
- (Skrytyy #1) Parallelno zaprashivaem /api/v2/synergy/board/data i ubezhdaemsya, chto naznachenie otrazhaetsya.
- (Skrytyy #2) Povtor s tem zhe X-Request-Id — tot zhe trace_id.

ZEMNOY ABZATs:
Proverka «kak u integratora»: odin HTTP-klient, podpis po HMAC, validnye otvety JSON i stabilnaya idempotentnost.

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
def prep(monkeypatch):
    # Nastroim podpis
    monkeypatch.setenv("P2P_SIGNING_REQUIRED","1")
    monkeypatch.setenv("P2P_HMAC_KEY","E2EKEY")
    # Chistaya pamyat
    STORE._agents.clear(); STORE._teams.clear()
    # Dannye
    STORE.upsert_agent({"id":"human.expert","kind":"human","profile":{"name":"Sergey","age":62,"exp_years":35,"domains":["aerorazvedka","taktika"]}})
    STORE.upsert_agent({"id":"human.pilot","kind":"human","profile":{"name":"Maksim","age":24,"exp_years":3,"domains":["upravlenie","drony"]}})
    STORE.upsert_agent({"id":"device.drone1","kind":"device","profile":{"name":"Scout-01","device":"drone","flight_time_min":28,"payload_g":200,"latency_ms":40}})
    STORE.create_team("Recon A","aerorazvedka",["strategist","operator","platform"])
    yield
    STORE._agents.clear(); STORE._teams.clear()

def test_assign_and_board_reflects():
    c = TestClient(app)
    path = "/api/v2/synergy/assign"
    body = b'{"team_id":"Recon A","overrides":{"operator":"human.pilot"}}'
    ts = int(time.time())
    sig = _sig("POST", path, body, os.environ["P2P_HMAC_KEY"], ts)
    hdr = {
        "Content-Type": "application/json",
        "X-P2P-Timestamp": str(ts),
        "X-P2P-Signature": sig,
        "X-Request-Id": "RID-E2E-1",
    }
    r1 = c.post(path, content=body, headers=hdr)
    assert r1.status_code == 200
    j1 = r1.json()
    assert j1["ok"] is True and j1["assigned"]["operator"] == "human.pilot"

    # borda
    b = c.get("/synergy/board/data?team_id=Recon%20A").json()
    assert b["ok"] is True
    assert b["assigned"].get("operator") == "human.pilot"

    # povtor tot zhe request-id — tot zhe trace
    r2 = c.post(path, content=body, headers=hdr).json()
    assert r2["trace_id"] == j1["trace_id"]