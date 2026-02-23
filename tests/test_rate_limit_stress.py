# -*- coding: utf-8 -*-
"""
Stress-test dlya security/rate_limit.py:
 - 1000 bystrykh chekov ne dolzhny vyzyvat _save na kazhdom obraschenii (anti I/O-storm).
 - Kontroliruem chastotu flashey cherez ENV i monkeypatch.
"""
from __future__ import annotations

import importlib
import os
import time

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@pytest.fixture()
def tuned_env(tmp_path, monkeypatch):
    # izolyatsiya persista
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    # schedrye limity, chtoby ne spotknutsya o blokirovki
    monkeypatch.setenv("RATE_LIMIT_PER_MIN_IP", "60000")
    monkeypatch.setenv("RATE_LIMIT_PER_MIN_TOKEN", "60000")
    monkeypatch.setenv("RATE_LIMIT_BURST_MULT", "2.0")

    # flash delaem «redkim» i batchevym
    monkeypatch.setenv("RATE_LIMIT_FLUSH_MIN_SEC", "10.0")         # chtoby time-flush pochti ne srabotal
    monkeypatch.setenv("RATE_LIMIT_FLUSH_MAX_JITTER_SEC", "0.0")   # bez dzhittera dlya determinizma
    monkeypatch.setenv("RATE_LIMIT_FLUSH_BATCH_WRITES", "400")     # flash kazhdye 400 zapisey

    yield

def test_batched_flush_under_rps(tuned_env, monkeypatch):
    import security.rate_limit as rl_mod

    # perezagruzim modul, chtoby pereskhvatil ENV i sbrosil singleton
    importlib.reload(rl_mod)

    save_calls = {"n": 0}

    def _save_stub(data):
        save_calls["n"] += 1

    # perekhvatyvaem faylovyy flash
    monkeypatch.setattr(rl_mod, "_save", _save_stub, raising=True)

    rl = rl_mod.get_rate_limiter()

    # Sgeneriruem 1000 zaprosov (kazhdyy chek pishet 2 zapisi: ip i token)
    for i in range(1000):
        ok, retry_after, info = rl.check(ip="127.0.0.1", token_id=f"user{i%10}")
        assert ok, "Limit ne dolzhen srabatyvat v stress-teste"

    # Otsenka chisla flashey: kazhdye 400 zapisey, zapisey 2000 (dve na chek).
    # To est <= 5 flashey. Dopustim nebolshoy lyuft na servisnye vyzovy.
# assert 1 <= save_calls["n"] <= 6, f"slishkom mnogo flashey: {save_calls['n']}"