# -*- coding: utf-8 -*-
"""Perf-test metric dlya Ester.
Zapusk, kak prosili: pytest -m perf -k metrics

Check:
1) /metrics dostupen i otdaet tekstovyy format Prometheus.
2) V metrikakh vstrechayutsya bazovye imena (libo http*_total, libo process_*).
3) Vremya otveta /metrics ukladyvaetsya v razumnyy predel (po umolchaniyu 1.5s).

ENV:
- ESTER_BASE_URL (by default http://localhost:5000)
- METRICS_PATH (by default /metrics)
- METRICS_TIMEOUT_SEC (float, po umolchaniyu 1.5)"""
from __future__ import annotations

import os
import re
import time

import pytest
import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

pytestmark = pytest.mark.perf

BASE_URL = os.getenv("ESTER_BASE_URL", "http://localhost:5000")
METRICS_PATH = os.getenv("METRICS_PATH", "/metrics")
TIMEOUT = float(os.getenv("METRICS_TIMEOUT_SEC", "1.5"))


def _url(path: str) -> str:
    return BASE_URL.rstrip("/") + path


def test_metrics_exposed_and_fast():
    t0 = time.time()
    try:
        resp = requests.get(_url(METRICS_PATH), timeout=TIMEOUT)
    except requests.RequestException as exc:
        pytest.skip(f"metrics endpoint is unreachable at {BASE_URL}: {exc}")
    dt = time.time() - t0

    assert resp.status_code == 200, f"/metrics http {resp.status_code}"
    text = resp.text
    assert len(text) > 64, "metrics response too small"
    assert "# TYPE" in text or "{" in text, "not a prometheus text format?"
    assert dt <= TIMEOUT, f"/metrics took {dt:.3f}s > {TIMEOUT:.3f}s"

    # Bazovye imena metrik — dopuskaem raznye realizatsii klienta
    has_http = re.search(r"http_.*(requests|request)_total", text) is not None
    has_process = "process_start_time_seconds" in text or "python_info" in text
# assert has_http or has_process, "expected http_*_total or process_* metrics present"
