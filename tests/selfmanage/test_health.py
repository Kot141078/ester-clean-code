# -*- coding: utf-8 -*-
"""tests/selfmanage/test_health.py - proverki health-prob.

MOSTY:
- (Yavnyy) DB i internal statusy formiruyutsya kak ok; http-proba - warn pri otsutstvii putey.
- (Skrytyy #1) summary() aggregate v overall.
- (Skrytyy #2) Rabotaet v izolyatsii tmp SQLite.

ZEMNOY ABZATs:
Garantiruet, chto samoproverki ne padayut i dayut konsistentnyy otchet.

# c=a+b"""
from __future__ import annotations

import os

import pytest

from modules.selfmanage.health import check_db, check_internal, check_http_paths, summary
from modules.synergy.state_store import STORE
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@pytest.fixture(autouse=True)
def iso_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNERGY_DB_PATH", str(tmp_path/"ester.db"))
    STORE._agents.clear(); STORE._teams.clear()
    yield
    STORE._agents.clear(); STORE._teams.clear()

def test_basic_checks(monkeypatch):
    d = check_db(); i = check_internal()
    assert d.status in ("ok","warn") and i.status in ("ok","warn")

def test_http_warn_when_not_configured(monkeypatch):
    monkeypatch.delenv("SELF_HEALTH_HTTP_PROBE", raising=False)
    h = check_http_paths()
    assert h.status == "warn"

def test_summary_ok(monkeypatch):
    monkeypatch.delenv("SELF_HEALTH_HTTP_PROBE", raising=False)
    s = summary()
    assert s["overall"] in ("ok","warn")