# -*- coding: utf-8 -*-
"""tests/health_metrics_smoke.py - smoke dlya health/readiness/metrics Ester messaging.

MOSTY:
- (Yavnyy) Registriruem rasshirnnyy nabor marshrutov i proveryaem otvety 200 i strukturu poley.
- (Skrytyy #1) Passivnaya proverka nalichiya ENV tokenov (boolean v otvete).
- (Skrytyy #2) Nalichie metrik v otdelnom reestre — ne konfliktuet s obschim /metrics.

ZEMNOY ABZATs:
Daet bystryy “zelenyy” signal SRE: service zhiv, gotov i nablyudaem.

# c=a+b"""
from __future__ import annotations
import os, pytest
from flask import Flask

from routes.messaging_register_all_plus import register as reg_plus
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@pytest.fixture
def app():
    os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "devcheck")
    app = Flask(__name__)
    reg_plus(app)
    app.testing = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_liveness(client):
    r = client.get("/messaging/liveness")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

def test_readiness(client):
    r = client.get("/messaging/readiness")
    assert r.status_code == 200
    j = r.get_json()
    assert "rules_loaded" in j and "will_map_loaded" in j

def test_health(client):
    r = client.get("/messaging/health")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert "telegram" in j and "whatsapp" in j

def test_metrics(client):
    r = client.get("/metrics/messaging")
    assert r.status_code == 200
    assert b"ester_msg_requests_total" in r.data