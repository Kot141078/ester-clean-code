# -*- coding: utf-8 -*-
import glob
import json
import os

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

pytestmark = [pytest.mark.perf]


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.skipif(
    os.getenv("ESTER_PERF_VERIFY", "0") != "1", reason="set ESTER_PERF_VERIFY=1 to run"
)
def test_perf_artifacts_thresholds():
    files = sorted(glob.glob("artifacts/perf/*.summary.json"))
    assert (
        files
    ), "net faylov artifacts/perf/*.summary.json — snachala zapusti bench"
    p95_limit = int(os.getenv("ESTER_P95_MS", "2000"))
    p99_limit = int(os.getenv("ESTER_P99_MS", "5000"))
    fail_rate_limit = float(os.getenv("ESTER_FAIL_RATE", "0.01"))

    errors = []
    for path in files:
        data = _load(path)
        metrics = data.get("metrics") or {}
        dur = metrics.get("http_req_duration", {}).get("values") or {}
        fail = metrics.get("http_req_failed", {}).get("values") or {}
        p95 = float(dur.get("p(95)", p95_limit))
        p99 = float(dur.get("p(99)", p99_limit))
        rate = float(fail.get("rate", 0.0))
        if p95 > p95_limit or p99 > p99_limit or rate > fail_rate_limit:
            errors.append((os.path.basename(path), p95, p99, rate))
    assert not errors, "Porog narushen: " + "; ".join(
        f"{name}: p95={p95:.1f}ms p99={p99:.1f}ms fail_rate={rate:.4f}"
        for name, p95, p99, rate in errors
)