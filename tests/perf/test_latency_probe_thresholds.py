# -*- coding: utf-8 -*-
import json
import os

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

pytestmark = [pytest.mark.perf]
ART_PATH = "artifacts/perf/latency_probe.json"


@pytest.mark.skipif(
    os.getenv("ESTER_LAT_PROBE_VERIFY", "0") != "1",
    reason="set ESTER_LAT_PROBE_VERIFY=1 to run",
)
def test_latency_probe_thresholds():
    assert os.path.exists(ART_PATH), f"{ART_PATH} not found — run scripts/latency_probe.py first"
    with open(ART_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    cfg = data.get("config", {})
    thr = cfg.get("thresholds") or {}
    p95_limit = float(os.getenv("ESTER_P95_MS", thr.get("p95_ms", 2000)))
    p99_limit = float(os.getenv("ESTER_P99_MS", thr.get("p99_ms", 5000)))
    fail_limit = float(os.getenv("ESTER_FAIL_RATE", thr.get("fail_rate", 0.01)))

    bad = []
    for r in data.get("results", []):
        if r["p95_ms"] > p95_limit or r["p99_ms"] > p99_limit or r["fail_rate"] > fail_limit:
            bad.append((r["name"], r["p95_ms"], r["p99_ms"], r["fail_rate"]))

    assert not bad, "Thresholds failed: " + "; ".join(
        f"{n}: p95={p95:.1f} p99={p99:.1f} fail={fr:.4f}" for n, p95, p99, fr in bad
)