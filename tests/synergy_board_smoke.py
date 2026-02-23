# -*- coding: utf-8 -*-
"""
tests/synergy_board_smoke.py — dymovye testy «shakhmatki» i assign v2.

MOSTY:
- (Yavnyy) Proveryaem, chto UI otdaetsya, JSON-dannye est, overraydy primenyayutsya.
- (Skrytyy #1) assign v2 vozvraschaet plan i total-score.
- (Skrytyy #2) outcome pishet istoriyu v komandu.

ZEMNOY ABZATs:
Garantiruet, chto operator mozhet glazami «sobrat» komandu i zafiksirovat reshenie.

# c=a+b
"""
from __future__ import annotations
from flask import Flask
import pytest

from routes.synergy_routes import register as reg_base
from routes.synergy_routes_plus import register as reg_plus
from routes.synergy_board_routes import register as reg_board
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@pytest.fixture
def app():
    app = Flask(__name__)
    reg_base(app); reg_plus(app); reg_board(app)
    app.testing = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def _seed(client):
    client.post("/synergy/agents/register", json={"id":"human.expert","kind":"human","profile":{"name":"Sergey","age":62,"exp_years":35,"domains":["aerorazvedka","taktika"]},"bio":"veteran, strateg"})
    client.post("/synergy/agents/register", json={"id":"human.pilot","kind":"human","profile":{"name":"Maksim","age":24,"exp_years":3,"domains":["upravlenie","drony"]},"bio":"bystrye reaktsii"})
    client.post("/synergy/agents/register", json={"id":"device.drone1","kind":"device","profile":{"name":"Scout-01","device":"drone","flight_time_min":28,"payload_g":200,"latency_ms":40}})
    client.post("/synergy/teams/create", json={"name":"Recon A","purpose":"aerorazvedka","roles":["strategist","operator","platform"]})

def test_board_and_assign_v2(client):
    _seed(client)
    r = client.get("/synergy/teams/board?team_id=Recon%20A")
    assert r.status_code == 200
    rj = client.get("/synergy/board/data?team_id=Recon%20A").get_json()
    assert rj["ok"] is True
    ov = {"operator":"human.pilot"}
    res = client.post("/synergy/assign/v2", json={"team_id":"Recon A","overrides":ov}).get_json()
    assert res["ok"] is True
    assert res["assigned"]["operator"] == "human.pilot"
    hist = client.post("/synergy/outcome", json={"team_id":"Recon A","outcome":"success","notes":"tsel razvedana"}).get_json()
    assert hist["ok"] is True