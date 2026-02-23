# -*- coding: utf-8 -*-
"""
tests/e2e_messaging_flow.py — skvoznoy test: preset → predprosmotr → proaktivnaya otpravka.

MOSTY:
- (Yavnyy) Registriruem vse blyuprinty v in-memory Flask i progonyaem tsepochku zaprosov.
- (Skrytyy #1) Routing po config/messaging_rules.yaml.
- (Skrytyy #2) Dry-run kanalov (WA/TG) bez vneshnego interneta — determinirovannye otvety.

ZEMNOY ABZATs:
Daet bystryy uverennyy signal, chto Ester mozhet «kak chelovek» sobrat tekst i korrektno
ego razoslat po nuzhnomu kanalu, ne lomaya nichego v proekte.

# c=a+b
"""
from __future__ import annotations
import os, io, json, tempfile
import pytest
from flask import Flask

# Importy registratorov iz ranee vydannykh paketov
from routes.whatsapp_webhook_routes import register as reg_wa_wh
from routes.whatsapp_send_routes import register as reg_wa_send
from routes.whatsapp_control_routes import register as reg_wa_ctrl
from routes.wa_style_admin import register as reg_wa_admin
from routes.telegram_webhook_routes import register as reg_tg_wh
from routes.telegram_send_routes import register as reg_tg_send
from routes.proactive_dispatch_routes import register as reg_proactive
from routes.mail_compose_routes import register as reg_mail
from routes.presets_routes import register as reg_presets
from routes.messaging_register_all import register as reg_reg
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@pytest.fixture
def app(tmp_path):
    # ENV dlya dry-run
    os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "devcheck")
    os.environ.pop("WHATSAPP_ACCESS_TOKEN", None)       # otsutstvuet => dry
    os.environ.pop("WHATSAPP_PHONE_NUMBER_ID", None)    # otsutstvuet => dry
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)          # otsutstvuet => dry

    # Sozdadim vremennyy fayl pravil marshrutizatsii
    rules_path = tmp_path / "messaging_rules.yaml"
    rules_path.write_text(
        """
routes:
  bank: { channel: whatsapp, to: "15550001122" }
  engineer: { channel: telegram, to: 777001 }
        """.strip(),
        encoding="utf-8",
    )
    os.environ["PROACTIVE_RULES_PATH"] = str(rules_path)

    app = Flask(__name__)
    # Registriruem vse trebuemye blyuprinty
    reg_wa_wh(app); reg_wa_send(app); reg_wa_ctrl(app); reg_wa_admin(app)
    reg_tg_wh(app); reg_tg_send(app)
    reg_proactive(app); reg_mail(app); reg_presets(app); reg_reg(app)
    app.testing = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_presets_list(client):
    r = client.get("/presets/list")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["count"] >= 10

def test_compose_and_dispatch_bank(client):
    # 1) Sobrat pismo po presetu
    r = client.post("/presets/compose", json={
        "preset":"bank.transfer_status",
        "facts":{"date":"02.10.2025","amount":"1 250 EUR","reference":"TR-84921","account":"BE68 5390 0754 7034"}
    })
    assert r.status_code == 200
    text = r.get_json()["text"]
    assert "Proshu podtverdit status perevoda" in text

    # 2) Predprosmotr pisma kak otdelnyy shag
    r2 = client.post("/mail/compose/preview", json={"audience":"bank","intent":"letter","content":"Proverka statusa perevoda TR-84921."})
    assert r2.status_code == 200
    j2 = r2.get_json()
    assert j2["ok"] is True
    assert "Zdravstvuyte" in j2["text"]

    # 3) Proaktivnaya otpravka (marshrut beretsya iz pravil)
    r3 = client.post("/proactive/dispatch", json={
        "audience":"bank","intent":"letter","content":"Proshu podtverdit status perevoda TR-84921.","source_id":"test-e2e-1"
    })
    assert r3.status_code == 200
    j3 = r3.get_json()
    assert j3["ok"] is True
    assert j3["channel"] == "whatsapp"

def test_dispatch_engineer_to_telegram(client):
    r = client.post("/proactive/dispatch", json={
        "audience":"engineer","intent":"update","content":"Status tiketa #123: gotovo.","source_id":"test-e2e-2"
    })
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["channel"] == "telegram"