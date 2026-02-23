# -*- coding: utf-8 -*-
"""
Proveryaet, chto observability/otel.py bezopasno rabotaet v okruzhenii bez OpenTelemetry.
"""

import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_otel_noop_without_packages(monkeypatch):
    # izoliruem sredu
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    from importlib import reload

    import observability.otel as otel

    # init i span ne dolzhny padat
    otel.init_otel(service_name="ester-test")
    with otel.span("unit-test", {"k": "v"}):
        otel.record_metric("ester.metric.test", 1.0, {"unit": "test"})

    # povtornyy import (reload) tozhe ne dolzhen lomatsya
# reload(otel)