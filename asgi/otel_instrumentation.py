# -*- coding: utf-8 -*-
"""asgi/otel_instrumentation.py - bezopasnaya obvyazka FastAPI/ASGI dlya treysinga/metrik.

MOSTY:
- (Yavnyy) instrument_app(app): vklyuchaet FastAPI-treysing (if SDK is available) i pishet latency-histogrammu/statusy.
- (Skrytyy #1) Vstroennyy middleware bez storonnikh zavisimostey; OTel SDK - optional.
- (Skrytyy #2) Sovmestim s security headers (Iter.10): poryadok obertok ne kritichen.

ZEMNOY ABZATs:
Odna stroka - i u tebya p95 latentnost `/api/v2/synergy/assign`, schetchik oshibok i status-kody po routam.

# c=a+b"""
from __future__ import annotations

import time
from typing import Callable

from fastapi import Request
from fastapi.responses import Response

from observability.otel import init_otel
from modules.synergy.metrics import record_api_status, record_assign_latency_ms
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def instrument_app(app):
    # Let's try to enable Hotel-instrumentation FastAPI (if SDK is installed)
    try:
        init_otel()
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        pass

    @app.middleware("http")
    async def _metrics_mw(request: Request, call_next: Callable):
        t0 = time.perf_counter()
        try:
            response: Response = await call_next(request)
            return response
        finally:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            path = request.url.path
            record_assign_latency_ms(dt_ms, {"path": path})
            try:
                record_api_status(path, int(getattr(response, "status_code", 0)))
            except Exception:
                pass

    return app