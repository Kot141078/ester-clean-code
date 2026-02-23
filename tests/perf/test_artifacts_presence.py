# -*- coding: utf-8 -*-
import glob
import os

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

pytestmark = [pytest.mark.perf]


@pytest.mark.skipif(
    os.getenv("ESTER_PERF_PRESENCE", "0") != "1",
    reason="set ESTER_PERF_PRESENCE=1 to run",
)
def test_perf_files_exist():
    summaries = glob.glob("artifacts/perf/*.summary.json")
    assert (
        summaries
    ), "Net artifacts/perf/*.summary.json — snachala progonite profili (make perf-all)"
    assert os.path.exists(
        "artifacts/perf/report.md"
    ), "Net artifacts/perf/report.md — zapustite perf_aggregate.py"
    assert os.path.exists(
        "artifacts/perf/aggregate.json"
), "Net artifacts/perf/aggregate.json — zapustite perf_aggregate.py"