# -*- coding: utf-8 -*-
"""routes/synergy_api_v2_mount.py - montirovanie FastAPI /api/v2 v suschestvuyuschiy Flask.

MOSTY:
- (Yavnyy) Oborachivaet ASGI (FastAPI) v WSGI cherez asgiref.wsgi.AsgiToWsgi i veshaet DispatcherMiddleware.
- (Skrytyy #1) A/B-flag SYNERGY_API_V2_ENABLE (by umolchaniyu vklyucheno).
- (Skrytyy #2) Prefiks montirovaniya nastraivaetsya ENV (SYNERGY_API_V2_PREFIX) bez izmeneniya koda.

ZEMNOY ABZATs:
Odna stroka v `app.py` - i novoe API dostupno, a staryy Flask ostaetsya kak byl.

# c=a+b"""
from __future__ import annotations

import os
from typing import Any

from werkzeug.middleware.dispatcher import DispatcherMiddleware
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def register(app: Any):
    if os.getenv("SYNERGY_API_V2_ENABLE", "1") != "1":
        app.logger.info("[api-v2] disabled by SYNERGY_API_V2_ENABLE")
        return app
    prefix = os.getenv("SYNERGY_API_V2_PREFIX", "/api/v2").rstrip("/")
    try:
        try:
            from asgiref.wsgi import AsgiToWsgi  # type: ignore
        except Exception:
            from asgi.asgi_to_wsgi import AsgiToWsgi  # type: ignore
        from asgi.synergy_api_v2 import app as asgi_app
        wsgi_sub = AsgiToWsgi(asgi_app)
        app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {prefix: wsgi_sub})
        app.logger.info("[api-v2] mounted at %s", prefix)
    except Exception as e:
        app.logger.warning("[api-v2] mount failed: %s", e, exc_info=True)
    return app