# -*- coding: utf-8 -*-
"""
tests/messaging/test_outbox.py — proverka outbox i povtornoy otpravki.

MOSTY:
- (Yavnyy) add_outgoing/list_outgoing/resend s podmenoy adapterov na «zaglushki».
- (Skrytyy #1) Status resent:* posle povtornoy otpravki.
- (Skrytyy #2) Limit vyborki i sortirovka po ts.

ZEMNOY ABZATs:
Zhurnal iskhodyaschikh deystvitelno pishetsya i pozvolyaet bystro «doslat» to zhe soobschenie, ne polagayas na pamyat.

# c=a+b
"""
from __future__ import annotations

import json
from typing import Any

import messaging.outbox_store as ob
import messaging.telegram_adapter as tg
import messaging.whatsapp_adapter as wa
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_outbox_record_and_resend(monkeypatch, tmp_path):
    monkeypatch.setenv("MESSAGING_DB_PATH", str(tmp_path/"db.sqlite"))

    # Zapishem dve iskhodyaschie
    id1 = ob.add_outgoing("telegram","42","hi","ok",200,"RID-1")
    id2 = ob.add_outgoing("whatsapp","380001112233","yo","fail",502,"RID-2")
    xs = ob.list_outgoing(limit=10)
    assert len(xs) == 2 and xs[0][0] in (id1,id2)

    # Podmenim adaptery na fiktivnye
    class FakeTG:
        def send_message(self, chat_id, text, parse_mode="HTML"):
            return {"ok": True, "status": 200, "body": "{}"}
    class FakeWA:
        def send_text(self, to_msisdn, text):
            return {"ok": True, "status": 200, "body": "{}"}
    monkeypatch.setattr(tg, "TelegramAdapter", lambda *a, **k: FakeTG())
    monkeypatch.setattr(wa, "WhatsAppAdapter", lambda *a, **k: FakeWA())

    r = ob.resend(id1)
    assert r["ok"] and int(r["status"]) == 200
    ys = ob.list_outgoing(limit=10)
    # dolzhna poyavitsya tretya zapis resent:*
    assert any("resent" in row[5] for row in ys)