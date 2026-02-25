# -*- coding: utf-8 -*-
"""tests/wa_smoke.py - isolated pytest-testy dlya WA-mosta.

MOSTY:
- (Yavnyy) Registration blyuprintov lokalno v testovom Flask-prilozhenii.
- (Skrytyy #1) Kontrakt /api/whatsapp/webhook (GET verify, POST inbound).
- (Skrytyy #2) Kontrakt /wa/send i /wa/ctrl/api/style/preview.

ZEMNOY ABZATs:
Testy ne trebuyut vneshnego interneta i realnykh klyuchey; gonyayutsya bystro i determinirovanno.

# c=a+b"""
from __future__ import annotations
import json
import os
import types
import pytest

from flask import Flask

# We import our blueprints directly.
from routes.whatsapp_webhook_routes import register as reg_webhook
from routes.whatsapp_send_routes import register as reg_send
from routes.whatsapp_control_routes import register as reg_ctrl
from routes.wa_style_admin import register as reg_admin
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@pytest.fixture
def app():
    os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "devcheck")
    from modules.persona_style import render_message  # smoke import
    app = Flask(__name__)
    reg_webhook(app)
    reg_send(app)
    reg_ctrl(app)
    reg_admin(app)
    app.testing = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_verify_ok(client):
    r = client.get("/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=devcheck&hub.challenge=42")
    assert r.status_code == 200
    assert r.get_data(as_text=True) == "42"

def test_verify_forbidden(client):
    r = client.get("/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=42")
    assert r.status_code == 403

def test_inbound_ok(client):
    sample = json.loads(open("tests/data/wa_webhook_sample.json","r",encoding="utf-8").read())
    r = client.post("/api/whatsapp/webhook", json=sample)
    assert r.status_code == 200
    j = r.get_json()
    assert j.get("ok") is True

def test_style_preview(client):
    r = client.post("/wa/ctrl/api/style/preview", json={
        "audience":"lawyer","intent":"letter","content":"I inform you that the meeting has been postponed to 15:00 tomorrow."
    })
    assert r.status_code == 200
    j = r.get_json()
    assert "render" in j
    assert "Dobryy den" in j["render"]

def test_send_dry_run(client):
    r = client.post("/wa/send?dry_run=1", json={
        "to":"15551234567",
        "audience":"friend",
        "intent":"update",
        "content":"See you at 18:30 at the entrance."
    })
    assert r.status_code == 200
    j = r.get_json()
    assert j.get("ok") is True
    assert j.get("dry_run") is True
    assert "text" in j