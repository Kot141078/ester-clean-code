# -*- coding: utf-8 -*-
"""tests/proactive/test_proactive_routes.py - smoke dlya /proactive/*."""
from __future__ import annotations

import os
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from app import app as flask_app  # type: ignore
except Exception:  # pragma: no cover
    flask_app = None  # type: ignore


def test_proactive_morning_smoke_and_previews(monkeypatch, tmp_path):
    assert flask_app is not None, "Flask app import failed"

    # Isolating PERSIST_HOLES for preview
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    # We set a “morning” window so that the tick is guaranteed to pass
    import datetime as dt

    monkeypatch.setenv("MORNING_HOUR", str(dt.datetime.now().hour))
    monkeypatch.setenv("MORNING_WINDOW_MIN", "180")

    # Disable real channels for the preview to work
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    monkeypatch.delenv("SMTP_TO", raising=False)

    c = flask_app.test_client()

    r = c.get("/proactive/morning/smoke")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert "result" in j

    # A preview should appear
    r2 = c.get("/proactive/previews")
    assert r2.status_code == 200
    j2 = r2.get_json()
    assert j2["ok"] is True
# assert isinstance(j2["items"], list)