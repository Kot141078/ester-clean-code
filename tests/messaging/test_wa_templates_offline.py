# -*- coding: utf-8 -*-
"""tests/messaging/test_wa_templates_offline.py - formirovanie WA template payload (bez seti).

MOSTY:
- (Yavnyy) Proveryaem sborku shablona s peremennymi i DRYRUN-otvet.
- (Skrytyy #1) Parametry yazyka/namespace berutsya iz YAML/ENV.
- (Skrytyy #2) Without realnogo tokena/phone_id (perekhvatyvaem konstruktor adaptera).

ZEMNOY ABZATs:
Garantiruet, chto "proaktivka" v WA idet legalnym sposobom - cherez templates, a payload sootvetstvuet Cloud API.

# c=a+b"""
from __future__ import annotations

import json
import os
import types

import messaging.wa_templates as wt
import messaging.whatsapp_adapter as wa
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_template_build_and_dryrun(monkeypatch, tmp_path):
    # local template directory
    p = tmp_path/"wa_templates.yaml"
    p.write_text("templates:\n  followup_meeting:\n    lang: ru\n    namespace: ns123\n", encoding="utf-8")
    monkeypatch.setenv("WA_TEMPLATES_CONFIG", str(p))
    monkeypatch.setenv("DEV_DRYRUN","1")
    # predotvraschaem sozdanie realnogo adaptera (trebuet token)
    class FakeA:
        phone_id="PID"; token="TOK"
    monkeypatch.setattr(wa, "WhatsAppAdapter", lambda : FakeA())
    r = wt.send_template("380001112233", "followup_meeting", ["Owner","12:30","zavtra"])
    assert r["ok"] and r["status"] == 200
    body = json.loads(r["body"])
    assert body["type"] == "template"
    assert body["template"]["name"] == "followup_meeting"
    assert body["template"]["language"]["code"] == "ru"
    assert body["template"]["namespace"] == "ns123"
    comps = body["template"]["components"][0]
    assert comps["type"] == "body" and len(comps["parameters"]) == 3