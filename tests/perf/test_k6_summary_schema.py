# -*- coding: utf-8 -*-
import glob
import json
import os

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

pytestmark = [pytest.mark.perf]
ART = "artifacts/perf"


@pytest.mark.skipif(
    os.getenv("ESTER_K6_SCHEMA_VERIFY", "0") != "1",
    reason="set ESTER_K6_SCHEMA_VERIFY=1 to run",
)
def test_k6_summary_has_core_keys():
    files = sorted(glob.glob(os.path.join(ART, "*.summary.json")))
    assert files, "no k6 summaries found — run perf profiles first"
    for p in files:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "metrics" in data and isinstance(data["metrics"], dict), f"{p}: no metrics"
        m = data["metrics"]
        for k in ("http_req_duration", "http_req_failed", "iterations", "http_reqs"):
            assert k in m, f"{p}: metric '{k}' missing"
# assert "values" in m[k], f"{p}: metric '{k}' has no 'values'"