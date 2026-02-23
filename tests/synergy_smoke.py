# -*- coding: utf-8 -*-
"""
tests/synergy_smoke.py — smoke dlya sinergii.

Mosty:
- (Yavnyy) Registriruem lyudey/dron, sozdaem komandu, naznachaem roli, proveryaem puls.
- (Skrytyy #1) Telemetriya uluchshaet profil bez oprosov.
- (Skrytyy #2) Notifikatsii bezopasny: po umolchaniyu dry.

Zemnoy abzats:
Bystro ubezhdaemsya, chto «starshiy strateg + molodoy operator + dron» formiruyut sbalansirovannuyu komandu.

# c=a+b
"""
from __future__ import annotations
import os, pytest
from flask import Flask
from routes.synergy_routes import register as reg_syn
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@pytest.fixture
def app():
    os.environ.setdefault("SYNERGY_NOTIFY","0")
    app = Flask(__name__)
    reg_syn(app)
    app.testing = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_full_flow(client):
    # expert
    client.post("/synergy/agents/register", json={"id":"human.expert","kind":"human","profile":{"name":"Sergey","age":62,"exp_years":35,"domains":["aerorazvedka","taktika"]},"bio":"veteran, strateg"})
    # pilot
    client.post("/synergy/agents/register", json={"id":"human.pilot","kind":"human","profile":{"name":"Maksim","age":24,"exp_years":3,"domains":["upravlenie","drony"]},"bio":"bystrye reaktsii"})
    # drone
    client.post("/synergy/agents/register", json={"id":"device.drone1","kind":"device","profile":{"name":"Scout-01","device":"drone","flight_time_min":28,"payload_g":200,"latency_ms":40}})

    # team
    client.post("/synergy/teams/create", json={"name":"Recon A","purpose":"aerorazvedka","roles":["strategist","operator","platform"]})
    r = client.post("/synergy/assign", json={"team_id":"Recon A"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert set(j["assigned"].keys()) == {"strategist","operator","platform"}

    p = client.get("/synergy/pulse?team_id=Recon%20A").get_json()
    assert p["ok"] is True
    assert p["coverage"] == 1.0