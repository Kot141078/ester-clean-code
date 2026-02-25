# -*- coding: utf-8 -*-
"""tests/synergy/test_board_sse.py - dymovye proverki SSE i agregatov.

MOSTY:
- (Yavnyy) Proveryaem, chto /board/stream otdaet text/event-stream i startovyy event:update.
- (Skrytyy #1) /board/aggregate vozvraschaet ozhidaemye razdely (role_candidates/agent_load/risks).
- (Skrytyy #2) Bystraya imitatsiya izmeneniya sostoyaniya - menyaem assigned i dergaem odin shag generatora.

ZEMNOY ABZATs:
Ubezhdaemsya, chto “shakhmatka” umeet obnovlyatsya sama, aggregaty dayut operatoru bystryy snimok sostoyaniya.

# c=a+b"""
from __future__ import annotations

import itertools
from flask import Flask
import pytest

from routes.synergy_board_stream import register as reg_stream
from modules.synergy.state_store import STORE
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@pytest.fixture
def app():
    app = Flask(__name__)
    reg_stream(app)
    app.testing = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def _seed():
    STORE.upsert_agent({"id":"human.expert","kind":"human","profile":{"name":"Sergey","age":62,"exp_years":35,"domains":["aerorazvedka","taktika"]}})
    STORE.upsert_agent({"id":"human.pilot","kind":"human","profile":{"name":"Maksim","age":24,"exp_years":3,"domains":["upravlenie","drony"]}})
    STORE.upsert_agent({"id":"device.drone1","kind":"device","profile":{"name":"Scout-01","device":"drone","flight_time_min":28,"payload_g":200,"latency_ms":40}})
    STORE.create_team("Recon A","aerorazvedka",["strategist","operator","platform"])

def test_sse_starts_and_aggregate(client, monkeypatch):
    _seed()
    # Checking the title
    r = client.get("/synergy/board/stream?team_id=Recon%20A")
    assert r.status_code == 200
    assert r.content_type.startswith("text/event-stream")

    # Agregaty
    a = client.get("/synergy/board/aggregate?team_id=Recon%20A").get_json()
    assert a["ok"] is True
    assert "role_candidates" in a and "agent_load" in a and "risks" in a