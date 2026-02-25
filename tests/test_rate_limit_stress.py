# -*- coding: utf-8 -*-
"""Stress-test dlya security/rate_limit.py:
 - 1000 bystrykh chekov ne dolzhny vyzyvat _save na kazhdom obraschenii (anti I/O-storm).
 - Kontroliruem often flashey cherez ENV i monkeypatch."""
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
    # generous limits to avoid tripping over blockages
    monkeypatch.setenv("RATE_LIMIT_PER_MIN_IP", "60000")
    monkeypatch.setenv("RATE_LIMIT_PER_MIN_TOKEN", "60000")
    monkeypatch.setenv("RATE_LIMIT_BURST_MULT", "2.0")

    # we make the flush “rare” and batch
    monkeypatch.setenv("RATE_LIMIT_FLUSH_MIN_SEC", "10.0")         # so that time-flush almost doesn’t work
    monkeypatch.setenv("RATE_LIMIT_FLUSH_MAX_JITTER_SEC", "0.0")   # no jitter for determinism
    monkeypatch.setenv("RATE_LIMIT_FLUSH_BATCH_WRITES", "400")     # flush every 400 records

    yield

def test_batched_flush_under_rps(tuned_env, monkeypatch):
    import security.rate_limit as rl_mod

    # reboot the module to re-catch the ENV and reset the singleton
    importlib.reload(rl_mod)

    save_calls = {"n": 0}

    def _save_stub(data):
        save_calls["n"] += 1

    # intercepts file flash
    monkeypatch.setattr(rl_mod, "_save", _save_stub, raising=True)

    rl = rl_mod.get_rate_limiter()

    # Generates 1000 requests (each check writes 2 entries: IP and token)
    for i in range(1000):
        ok, retry_after, info = rl.check(ip="127.0.0.1", token_id=f"user{i%10}")
        assert ok, "The limit should not be triggered in a stress test"

    # Estimated number of flushes: every 400 entries, 2000 entries (two per check).
    # That is <= 5 flushes. We will allow a small gap for service calls.
# assertion 1 <= save_callsew"n"sch <= 6, f"too many flushes: ZZF0Z"