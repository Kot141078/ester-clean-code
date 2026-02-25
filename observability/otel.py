# -*- coding: utf-8 -*-
"""observability.otel - initsializatsiya OpenTelemetry (treysy/metriki) s no-op folbekom.

MOSTY:
- Yavnyy: init_otel()/instrument_flask_app()/record_metric() — edinaya tochka podklyucheniya telemetrii.
- Skrytyy #1: (ENV ↔ SDK) — pri otsutstvii SDK ili OTEL_ENABLE=0 vse rabotaet v no-op rezhime, bez padeniy.
- Skrytyy #2: (REST ↔ Metriki) — record_metric() pozvolyaet pisat metriki iz lyubykh routov bez pryamoy zavisimosti.

ZEMNOY ABZATs:
Eto “schetchik na valu”: esli OTEL est - otdaem signaly naruzhu; net - tikho schitaem vkholostuyu.
Nikakoy seti ne trebuetsya po umolchaniyu, konfig eksporterov - cherez ENV.
# c=a+b"""
from __future__ import annotations

from contextlib import contextmanager
import os
from typing import Any, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_OTEL_READY: bool = False
_TRACER: Any = None
_METER: Any = None
_HISTOS: Dict[str, Any] = {}
_INSTRUMENTED: bool = False

def _env_bool(name: str, default: bool = True) -> bool:
    v = (os.getenv(name, "1" if default else "0") or "").strip().lower()
    return v in ("1", "true", "on", "yes", "y", "t")

def init_otel(service_name: Optional[str] = None) -> bool:
    """Initializes tracing/metric providers if SDK is available.
    Returns Three in full mode, otherwise False (but-op)."""
    global _OTEL_READY, _TRACER, _METER
    if _OTEL_READY:
        return True
    if not _env_bool("OTEL_ENABLE", True):
        _OTEL_READY = False
        return False
    try:
        from opentelemetry import metrics, trace  # type: ignore
        from opentelemetry.sdk.resources import Resource  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore
        from opentelemetry.sdk.metrics import MeterProvider  # type: ignore
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter  # type: ignore
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader  # type: ignore
    except Exception:
        _OTEL_READY = False
        return False

    svc = service_name or os.getenv("OTEL_SERVICE_NAME", "ester-api")
    resource = Resource.create({"service.name": svc})

    # Traces
    tp = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
    )
    tp.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tp)
    _TRACER = trace.get_tracer(svc)

    # Metrics (optsionalno)
    if _env_bool("OTEL_METRICS_ENABLE", True):
        metric_exporter = OTLPMetricExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/metrics")
        )
        reader = PeriodicExportingMetricReader(metric_exporter)
        mp = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(mp)
        _METER = metrics.get_meter(svc)

    _OTEL_READY = True
    return True

def instrument_flask_app(app: Any) -> bool:
    """Secure connection of Flask auto-interception (if the toolkit is installed)."""
    global _INSTRUMENTED
    if _INSTRUMENTED:
        return True
    if not _env_bool("OTEL_FLASK_AUTO", True):
        return False
    try:
        from opentelemetry.instrumentation.flask import FlaskInstrumentor  # type: ignore
        FlaskInstrumentor().instrument_app(app)
        _INSTRUMENTED = True
        return True
    except Exception:
        return False

def get_tracer() -> Any:
    if not _OTEL_READY or _TRACER is None:
        return _NoopTracer()
    return _TRACER

def get_meter() -> Any:
    if not _OTEL_READY or _METER is None:
        return _NoopMeter()
    return _METER

def record_metric(name: str, value: float, attributes: Optional[Dict[str, Any]] = None) -> None:
    """Unified recording of numerical metrics (Histogram). In no-op mode, it returns quietly."""
    m = get_meter()
    try:
        h = _HISTOS.get(name)
        if h is None:
            h = m.create_histogram(name)  # type: ignore[no-untyped-call]
            _HISTOS[name] = h
        h.record(float(value), attributes=attributes or {})  # type: ignore[no-untyped-call]
    except Exception:
        # in no-op and in the absence of SDK we simply do nothing
        pass


@contextmanager
def span(name: str, attributes: Optional[Dict[str, Any]] = None):
    tracer = get_tracer()
    with tracer.start_as_current_span(name, attributes=attributes or {}) as active:
        yield active

# ---------------- no-op klassy ----------------

class _NoopSpan:
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False
    def set_attribute(self, key, value): return self

class _NoopTracer:
    def start_as_current_span(self, name, **kw): return _NoopSpan()

class _NoopCounter:
    def add(self, v: float, attributes: dict | None = None): pass

class _NoopHistogram:
    def record(self, v: float, attributes: dict | None = None): pass

class _NoopUpDownCounter:
    def add(self, v: float, attributes: dict | None = None): pass

class _NoopMeter:
    def create_counter(self, *_a, **_k): return _NoopCounter()
    def create_histogram(self, *_a, **_k): return _NoopHistogram()
    def create_up_down_counter(self, *_a, **_k): return _NoopUpDownCounter()
