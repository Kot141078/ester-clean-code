# -*- coding: utf-8 -*-
"""
routes/proactive_dispatch_auto_patch.py - A/B-patch avtopodbora auditorii dlya /proactive/dispatch.

MOSTY:
- (Yavnyy) Pered samim endpointom perekhvatyvaet POST /proactive/dispatch, esli audience ne zadana/neytralna,
  i podstavlyaet auditoriyu cherez modules.audience_infer.infer_audience, zatem delegiruet v tot zhe endpoint.
- (Skrytyy #1) A/B vklyuchenie cherez ENV DISPATCH_AUTO_AUDIENCE=1 (po umolchaniyu vklyucheno).
- (Skrytyy #2) Predokhranitel ot rekursii cherez sluzhebnyy zagolovok DISPATCH_AUTO_HEADER.

ZEMNOY ABZATs:
Delaet «kak prosili» - avto-opredelenie lyudey/organizatsiy po tekstu/meta bez tupykh oprosov,
ne menyaya kontraktov i ne perepisyvaya uzhe gotovyy endpoint.

# c=a+b
"""
from __future__ import annotations
import os, json
from typing import Any, Dict
from flask import Blueprint, request, Response, current_app

from modules.audience_infer import infer_audience
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("proactive_dispatch_auto_patch", __name__)

AUTO_ON = os.getenv("DISPATCH_AUTO_AUDIENCE", "1") == "1"
AUTO_HDR = os.getenv("DISPATCH_AUTO_HEADER", "X-Ester-Dispatch-Auto")

@bp.before_app_request
def _auto_patch_before():
    if not AUTO_ON:
        return None
    if request.method != "POST":
        return None
    if request.path != "/proactive/dispatch":
        return None
    if request.headers.get(AUTO_HDR):
        return None  # uzhe obrabotano

    try:
        payload: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    except Exception:
        return None

    audience = (payload.get("audience") or "").strip().lower()
    content = (payload.get("content") or "").strip()
    meta = payload.get("meta") or {}

    # Esli auditoriya uzhe zadana yavno i ne "neutral" - ne vmeshivaemsya
    if audience and audience not in ("", "neutral"):
        return None

    # Pytaemsya vyvesti auditoriyu iz teksta/meta
    detected, conf = infer_audience(meta=meta, text=content)
    if not detected or conf < 0.2:
        return None  # slabyy signal - puskaem kak est

    # Peresobiraem JSON i delegiruem vnutr togo zhe endpointa cherez loopback
    payload["audience"] = detected
    try:
        body = json.dumps(payload).encode("utf-8")
        import urllib.request
        req = urllib.request.Request(
            "http://127.0.0.1:8080/proactive/dispatch",
            data=body,
            headers={"Content-Type": "application/json", AUTO_HDR: "1"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = resp.read()
            return Response(data, status=resp.getcode(), mimetype=resp.headers.get_content_type())
    except Exception as e:
        current_app.logger.warning("[DISPATCH-AUTO] delegate failed: %s", e, exc_info=True)
        return None  # ne meshaem shtatnoy obrabotke

def register(app):
    app.register_blueprint(bp)
    return bp