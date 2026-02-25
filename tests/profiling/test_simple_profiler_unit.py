# -*- coding: utf-8 -*-
"""tesc/profiling/test_simple_profiler_unit.po - units for percentile/matrix.
No real HTTP requests."""
from __future__ import annotations

from profiling.simple_profiler import Metrics, percentile
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_percentile_basic():
    assert percentile([], 95.0) == 0.0
    assert percentile([1.0], 95.0) == 1.0
    data = [1, 2, 3, 4, 5, 100]
    p95 = percentile(data, 95.0)
    assert p95 >= 5
    assert p95 <= 100


def test_metrics_accumulation():
    m = Metrics()
    # errors
    m.add(-1, 10.0)
    # 2xx
    m.add(200, 5.0)
    m.add(204, 7.0)
    # 401/403
    m.add(401, 9.0)
    m.add(403, 11.0)
    # prochee
    m.add(500, 15.0)

    d = m.to_dict()
    assert d["total"] == 6
    assert d["ok2xx"] == 2
    assert d["auth_fail"] == 2
    assert d["errors"] == 1
    assert d["other"] == 1
    assert d["lat_max_ms"] >= d["lat_avg_ms"]
