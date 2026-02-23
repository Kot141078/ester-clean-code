# -*- coding: utf-8 -*-
"""
tests/proactive/test_morning_digest_smoke.py — smoke-test utrennego daydzhesta.

Proveryaem:
- Okno utra (cherez ENV), bez TG/SMTP ukhodit v prevyu (publish_tg_preview zamokan)
- Idempotentnost: vtoroy tik v tot zhe den ne otpravlyaet povtorno
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List

import pytest

import proactive_notifier as pn  # tipy i klass iz koda daydzhesta
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class FakeMM:
    def __init__(self):
        self.meta: Dict[str, Dict[str, Any]] = {}
        self._emo = [{"emotions": {"calm": 0.8, "focus": 0.6}, "ts": time.time()}]
        self._fb = [
            {"text": "Vcherashnyaya zametka: protolknut MR po RBAC"},
            {"text": "Ideya: dobavit CRDT dlya P2P-kartochek"},
            {"text": "Son: agenty dogovorilis o plane dnya"},
        ]

    def get_session_meta(self, user: str, key: str):
        return self.meta.get(f"{user}:{key}", {})

    def set_session_meta(self, user: str, key: str, value: Dict[str, Any]):
        self.meta[f"{user}:{key}"] = value

    def get_emotions_journal(self, user: str, limit: int = 1):
        return self._emo[:limit]

    def flashback(self, query: str, k: int = 3):
        return self._fb[:k]

    # Dlya UI initsiativ (drugoy test)
    def get_agenda(self, user: str):
        return [{"id": "1", "title": "Proverit bekap", "status": "pending"}]

    def mark_offer(self, user: str, oid: str, status: str):
        return True

    def snooze_offer(self, user: str, oid: str, minutes: int):
        return True


def test_morning_digest_tick_preview(monkeypatch):
    # Nastroim okno «utra» na tekuschiy chas, chtoby tik srabotal
    import datetime as dt

    local_hour = dt.datetime.now().hour
    monkeypatch.setenv("MORNING_HOUR", str(local_hour))
    monkeypatch.setenv("MORNING_WINDOW_MIN", "120")

    # Otklyuchim TG/SMTP chtoby poshel fallback preview
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    monkeypatch.delenv("SMTP_TO", raising=False)

    # Zamokaem publish_tg_preview
    calls = {}

    def fake_preview(text: str):
        calls["text"] = text
        return {"ok": True, "path": "/tmp/ester_preview.txt"}

    pn.publish_tg_preview = fake_preview  # type: ignore

    mm = FakeMM()
    d = pn.MorningDigestDaemon(mm, providers=None, tg_token=None, default_user="Owner")

    res1 = d._tick()
    assert res1["ok"] is True
    assert res1["sent"] is True
    assert res1["channel"] == "preview"
    assert "path" in res1.get("preview", {}) or "preview" in res1

    # Povtor v tot zhe den — ne dolzhen otpravlyat
    res2 = d._tick()
    assert res2["ok"] is True
    assert res2["sent"] is False
    assert res2.get("reason") == "already_sent_today"
