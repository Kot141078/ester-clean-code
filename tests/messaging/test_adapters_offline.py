# -*- coding: utf-8 -*-
"""tests/messaging/test_adapters_offline.py - formirovanie zaprosov bez seti.

MOSTY:
- (Yavnyy) Pereopredelyaem setevye funktsii na zaglushki i proveryaem payload/URL.
- (Skrytyy #1) Proveryaem persona_prefix “assistent”.
- (Skrytyy #2) Normalizatsiya vkhodyaschikh iz webhook.

ZEMNOY ABZATs:
Pokryvaem osnovnoe: what otpravlyaem i kak chitaem. Bez realnykh tokenov/vneshney seti.

# c=a+b"""
from __future__ import annotations

import json
import os

import messaging.telegram_adapter as tg
import messaging.whatsapp_adapter as wa
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_telegram_send_build(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN","TEST")
    monkeypatch.setenv("TG_BOT_NAME","Ester")
    monkeypatch.setenv("MSG_TRANSPARENT_ID","1")
    sent = {}
    def fake_post(url, data, timeout=8.0):
        sent["url"] = url; sent["data"] = data; return 200, json.dumps({"ok":True})
    monkeypatch.setattr(tg, "_post", fake_post)
    a = tg.TelegramAdapter()
    r = a.send_message(42, "privet")
    assert r["ok"] and "sendMessage" in sent["url"]
    assert sent["data"]["text"].startswith("Ester · assistent:")

def test_whatsapp_send_build(monkeypatch):
    monkeypatch.setenv("WA_PHONE_ID","PID")
    monkeypatch.setenv("WA_TOKEN","TOK")
    monkeypatch.setenv("WA_BUSINESS_NAME","Ester")
    monkeypatch.setenv("MSG_TRANSPARENT_ID","1")
    sent = {}
    def fake_post(url, data, token, timeout=8.0):
        sent["url"]=url; sent["data"]=data; return 200, "{}"
    monkeypatch.setattr(wa, "_post", fake_post)
    a = wa.WhatsAppAdapter()
    r = a.send_text("380001112233", "privet")
    assert r["ok"] and "PID/messages" in sent["url"]
    assert sent["data"]["text"]["body"].startswith("Ester · assistent:")

def test_parsers():
    # Telegram
    t_upd = {"update_id":1,"message":{"date":1,"text":"hi","chat":{"id":7},"from":{"id":9}}}
    t = tg.TelegramAdapter.parse_update(t_upd)
    assert t and t["channel"]=="telegram" and t["chat_id"]==7

    # WhatsApp
    w_upd = {"entry":[{"changes":[{"value":{"messages":[{"type":"text","from":"123","text":{"body":"yo"}}]}}]}]}
    w = wa.WhatsAppAdapter.parse_update(w_upd)
    assert w and w["channel"]=="whatsapp" and w["chat_id"]=="123"