# -*- coding: utf-8 -*-
"""routes/metrics_ingest_bp_routes.py - Prometheus ekspozitsiya backpressure.

Endpoint:
  • GET /metrics/ingest_backpressure

Export:
  - ingest_allowed_total <count>
  - ingest_blocked_total <count>

Mosty:
- Yavnyy: (Nablyudaemost v†" Nagruzka) vidim vliyanie limitera na potok.
- Skrytyy #1: (Kibernetika v†" R egulyatsiya) mozhno alertit na vspleski blocked.
- Skrytyy #2: (Inzheneriya v†" Ekspluatatsiya) otdelnyy put - ne konfliktuet s obschimi metrikami.

Zemnoy abzats:
Eto para schetchikov u vorot: skolko mashin proekkhalo Re skolko zavernuli.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, Response, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_metrics_ingest_bp = Blueprint("metrics_ingest_bp", __name__)

try:
    from modules.ingest.backpressure import counters  # type: ignore
except Exception:
    counters = None  # type: ignore

def register(app):
    app.register_blueprint(bp_metrics_ingest_bp)

@bp_metrics_ingest_bp.route("/metrics/ingest_backpressure", methods=["GET"])
def metrics():
    if counters is None:
        return Response("ingest_allowed_total 0\ningest_blocked_total 0\n", mimetype="text/plain; version=0.0.4; charset=utf-8")
    c = counters() or {}
    body = f"ingest_allowed_total {int(c.get('allowed', 0))}\ningest_blocked_total {int(c.get('blocked', 0))}\n"
# return Response(body, mimetype="text/plain; version=0.0.4; charset=utf-8")