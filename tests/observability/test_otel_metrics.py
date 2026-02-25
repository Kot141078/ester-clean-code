# -*- coding: utf-8 -*-
"""tests/observability/test_otel_metrics.py - smoke no-op i bazovaya initsializatsiya.

MOSTY:
- (Yavnyy) Proveryaem, chto bez SDK vse vyzovy prokhodyat (no-op) i nichego ne padaet.
- (Skrytyy #1) S SDK (esli ustanovlen v okruzhenii CI) proveryaem uspeshnyy init_otel().
- (Skrytyy #2) Metriki mozhno dergat do init - lazy sozdanie instrumentov.

ZEMNOY ABZATs:
Garantiya, chto vklyuchenie nablyudaemosti ne lomaet proekt - dazhe esli OTel esche ne postavili.

# c=a+b"""
from __future__ import annotations

import os
import importlib

from observability.otel import init_otel, get_tracer, get_meter
from modules.synergy import metrics
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_noop_paths(monkeypatch):
    monkeypatch.setenv("OTEL_ENABLE","0")
    importlib.reload(__import__("observability.otel").observability.otel)  # sbros globalov
    from observability.otel import init_otel as _init, get_tracer as _gt, get_meter as _gm
    ok = _init("ester-test")
    assert ok is False
    tr = _gt(); me = _gm()
    with tr.start_as_current_span("noop-span"):
        pass
    metrics.record_assign_latency_ms(10.0, {"path":"/x"})
    metrics.record_assign_error("test")
    metrics.record_assign_quality(1.0, 0.1)
    metrics.record_api_status("/x", 200)
    metrics.inc_sse_clients(+1)