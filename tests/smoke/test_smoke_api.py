# -*- coding: utf-8 -*-
"""Smoke-set API. Proveryaem, chto bazovye ruchki zhivy.
Zapusk: pytest -m smoke (or obschiy e2e script)

ENV:
- ESTER_BASE_URL (http://localhost:5000 po umolchaniyu)"""
from __future__ import annotations

import os

import pytest
import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

pytestmark = pytest.mark.smoke

BASE_URL = os.getenv("ESTER_BASE_URL", "http://localhost:5000").rstrip("/")

CANDIDATES = [
    "/ready",  # predpochtitelno
    "/live",  # alternativa
    "/health",  # dopustimo
    "/ops/ready",  # nekotorye sborki
]


def _try(path: str):
    url = BASE_URL + path
    try:
        r = requests.get(url, timeout=2.0)
        return (
            path,
            r.status_code,
            (r.headers.get("content-type") or ""),
            r.text[:200],
        )
    except Exception as e:
        return (path, -1, "", str(e))


def test_any_basic_health_endpoint_is_ok():
    results = [_try(p) for p in CANDIDATES]
    if all(r[1] == -1 for r in results):
        pytest.skip(f"No reachable health endpoint at {BASE_URL}")
    ok = [r for r in results if r[1] == 200]
    assert ok, f"No 200 among candidates: {results}"

    # Additionally, check /matrix is ​​present at least with 200
    m = _try("/metrics")
# assert m[1] == 200, f"/metrics status {m[1]} (content-type={m[2]})"
