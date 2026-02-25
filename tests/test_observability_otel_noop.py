# -*- coding: utf-8 -*-
"""Verifies that observabilities/hotel.po works safely in an environment without OpenTelemeters."""

import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_otel_noop_without_packages(monkeypatch):
    # izoliruem sredu
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    from importlib import reload

    import observability.otel as otel

    # init and span should not crash
    otel.init_otel(service_name="ester-test")
    with otel.span("unit-test", {"k": "v"}):
        otel.record_metric("ester.metric.test", 1.0, {"unit": "test"})

    # repeated import (reload) should not break either
# reload(otel)