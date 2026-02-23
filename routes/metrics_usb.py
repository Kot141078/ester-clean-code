# -*- coding: utf-8 -*-
"""
routes/metrics_usb.py - Prometheus-metriki dlya USB-agenta (pull-model).

Marshruty:
  • GET /metrics/usb - tekst v formate Prometheus exposition (content-type text/plain; version=0.0.4)

Eksportiruemye metriki (labels: none):
  ester_usb_events_total        - chislo sobytiy v okne
  ester_usb_events_ok_total     - chislo uspeshnykh podgotovok
  ester_usb_events_err_total    - chislo oshibok
  ester_usb_latency_seconds_p50 - kvantil p50
  ester_usb_latency_seconds_p95 - kvantil p95
  ester_usb_last_timestamp      - unix-ts poslednego sobytiya

Mosty:
- Yavnyy (Kibernetika ↔ Nablyudenie): metriki - osnova adaptatsii taymingov/kvot.
- Skrytyy 1 (Infoteoriya ↔ Szhatie): kvantilnyy eksport → maksimum polzy na minimum strok.
- Skrytyy 2 (Inzheneriya ↔ Ekspluatatsiya): Prometheus-sovmestimost - srazu goditsya dlya alertov.

Zemnoy abzats:
Prometheus-zabor daet operatoru «puls» refleksa vstavki USB. Piki p95 - signal uvelichit taymaut ili dzhitter.

# c=a+b
"""
from __future__ import annotations

from flask import Blueprint, Response
import os
from metrics.usb_agent_stats import USBStats  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_metrics_usb = Blueprint("metrics_usb", __name__)

def _expose_line(name: str, value) -> str:
    try:
        v = float(value)
    except Exception:
        v = 0.0
    return f"{name} {v}\n"

@bp_metrics_usb.get("/metrics/usb")
def metrics_usb() -> Response:
    s = USBStats()
    snap = s.snapshot()
    lines = []
    # HELP/TYPE (dlya udobstva otladki; Prometheus eto sest)
    lines.append("# HELP ester_usb_events_total Number of USB events in window\n")
    lines.append("# TYPE ester_usb_events_total counter\n")
    lines.append(_expose_line("ester_usb_events_total", snap.get("count", 0)))
    lines.append("# HELP ester_usb_events_ok_total Number of OK events (cumulative)\n")
    lines.append("# TYPE ester_usb_events_ok_total counter\n")
    lines.append(_expose_line("ester_usb_events_ok_total", snap.get("ok", 0)))
    lines.append("# HELP ester_usb_events_err_total Number of ERR events (cumulative)\n")
    lines.append("# TYPE ester_usb_events_err_total counter\n")
    lines.append(_expose_line("ester_usb_events_err_total", snap.get("err", 0)))
    lines.append("# HELP ester_usb_latency_seconds_p50 50th percentile latency\n")
    lines.append("# TYPE ester_usb_latency_seconds_p50 gauge\n")
    lines.append(_expose_line("ester_usb_latency_seconds_p50", snap.get("p50", 0.0)))
    lines.append("# HELP ester_usb_latency_seconds_p95 95th percentile latency\n")
    lines.append("# TYPE ester_usb_latency_seconds_p95 gauge\n")
    lines.append(_expose_line("ester_usb_latency_seconds_p95", snap.get("p95", 0.0)))
    lines.append("# HELP ester_usb_last_timestamp Last event unix timestamp\n")
    lines.append("# TYPE ester_usb_last_timestamp gauge\n")
    lines.append(_expose_line("ester_usb_last_timestamp", snap.get("last_ts", 0)))
    body = "".join(lines)
    return Response(body, status=200, mimetype="text/plain; version=0.0.4; charset=utf-8")
# c=a+b


def register(app):
    app.register_blueprint(bp_metrics_usb)
    return app