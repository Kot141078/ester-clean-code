# -*- coding: utf-8 -*-
"""
tests/smoke/test_memory_journal_routes_alias.py

Smoke-testy dlya routes.memory_journal_routes_alias:
  - importiruetsya bez oshibok
  - register(app) registriruet blyuprint
  - /memory/journal/ping i /memory/journal/event otvechayut 200 pri nalichii modules.memory.events

Zapusk iz kornya proekta:
  pytest tests/smoke/test_memory_journal_routes_alias.py -q
"""
from __future__ import annotations

import os
import sys
import importlib

import pytest
from flask import Flask
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Koren proekta v sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_import_and_register():
    m = importlib.import_module("routes.memory_journal_routes_alias")
    assert hasattr(m, "bp")
    assert hasattr(m, "register")

    app = Flask("test_app_memory_journal")
    m.register(app)

    assert "memory_journal_routes_alias" in app.blueprints

    # Est li kanonicheskiy zhurnal
    have_events = False
    try:
        ev = importlib.import_module("modules.memory.events")
        have_events = hasattr(ev, "record_event")
    except Exception:
        have_events = False

    client = app.test_client()
    r = client.get("/memory/journal/ping")
    assert r.is_json
    data = r.get_json()
    assert "slot" in data

    if have_events:
        assert r.status_code == 200
        r2 = client.post(
            "/memory/journal/event",
            json={"kind": "test", "op": "smoke", "ok": True, "info": {"k": "v"}},
        )
        assert r2.status_code == 200
        d2 = r2.get_json()
        assert d2.get("ok") is True
        assert d2.get("event")
    else:
        # pri otsutstvii events alias chestno soobschaet ob oshibke
        assert data.get("ok") is False