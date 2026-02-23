# -*- coding: utf-8 -*-
"""
metrics/messaging_metrics.py — Prometheus metriki dlya messaging.

MOSTY:
- (Yavnyy) /metrics/messaging s otdelnym registry (bez vmeshatelstva v obschiy /metrics).
- (Skrytyy #1) Middleware-instrumentatsiya /wa/*, /tg/*, /proactive/* — latency + kod otveta.
- (Skrytyy #2) Leybly kanal/status dlya otpravok — agregiruyutsya po puti i kodu (ne chitaem telo otveta).

ZEMNOY ABZATs:
Pozvolyaet monitorit «zdorove rechi» Ester: skolko soobscheniy ushlo, skolko upalo, medlennye li otvety.

# c=a+b
"""
from __future__ import annotations
import time
from typing import Optional

from flask import Blueprint, request, Response, current_app, g
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("messaging_metrics", __name__)

REG = CollectorRegistry()

REQS = Counter("ester_msg_requests_total", "Messaging requests count", ["path_group", "code"], registry=REG)
LAT = Histogram("ester_msg_request_seconds", "Messaging request duration seconds",
                buckets=(0.05,0.1,0.25,0.5,1,2,5,10), labelnames=["path_group"], registry=REG)

def _group(path: str) -> str:
    if path.startswith("/wa/"):
        return "wa"
    if path.startswith("/api/whatsapp/"):
        return "wa_webhook"
    if path.startswith("/tg/"):
        return "tg"
    if path.startswith("/api/telegram/"):
        return "tg_webhook"
    if path.startswith("/proactive/"):
        return "proactive"
    return "other"

@bp.before_app_request
def before():
    g.__msg_t0 = time.time()
    g.__msg_grp = _group(request.path)

@bp.after_app_request
def after(resp: Response):
    try:
        grp = getattr(g, "__msg_grp", "other")
        dt = max(0.0, time.time() - getattr(g, "__msg_t0", time.time()))
        LAT.labels(grp).observe(dt)
        REQS.labels(grp, str(resp.status_code)).inc()
    except Exception as e:
        current_app.logger.debug("metrics err: %s", e)
    return resp

@bp.route("/metrics/messaging", methods=["GET"])
def metrics():
    data = generate_latest(REG)
    return Response(data, mimetype=CONTENT_TYPE_LATEST)

def register(app):
    app.register_blueprint(bp)
    return bp