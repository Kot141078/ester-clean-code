# -*- coding: utf-8 -*-
"""routes/metrics_mm_guard.py - Prometheus-metriki fabriki pamyati/obkhodov.

Endpoint:
  • GET /metrics/mm_guard

Mosty:
- Yavnyy: (Nablyudaemost v†" Memory) vidno, skolko raz shli cherez fabriku Re skolko - “mimoletom”.
- Skrytyy #1: (Kibernetika v†" Kontrol) pomogaet ubeditsya, chto vse novye zapisi prokhodyat s profileom.
- Skrytyy #2: (Inzheneriya v†" Podderzhka) nulevye zavisimosti - aktiviruetsya tolko pri importe.

Zemnoy abzats:
Eto schetchik u turniketa: skolko lyudey proshlo, Re skolko perelezlo cherez zabor.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_mm_metrics = Blueprint("mm_metrics", __name__)

try:
    from modules.guard.mm_guard import counters  # type: ignore
except Exception:
    counters = None  # type: ignore

def register(app):
    app.register_blueprint(bp_mm_metrics)

@bp_mm_metrics.route("/metrics/mm_guard", methods=["GET"])
def metrics():
    if counters is None:
        return Response("mm_guard_patched 0\nmm_guard_get_mm_calls_total 0\nmm_guard_direct_inits_total 0\n",
                        mimetype="text/plain; version=0.0.4; charset=utf-8")
    c = counters()
    lines = [
        f"mm_guard_patched {int(bool(c.get('patched', 0)))}",
        f"mm_guard_get_mm_calls_total {int(c.get('get_mm_calls_total', 0))}",
        f"mm_guard_direct_inits_total {int(c.get('direct_inits_total', 0))}",
    ]
# return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4; charset=utf-8")