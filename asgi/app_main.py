# -*- coding: utf-8 -*-
"""asgi/app_main.py - edinaya tochka vkhoda ASGI (FastAPI API v2 + Flask SSE/borda).

MOSTY:
- (Yavnyy) Montiruem FastAPI-prilozhenie asgi.synergy_api_v2.app i WSGI-Flask s potokovymi SSE i shablonami.
- (Skrytyy #1) Korrektiruem url_prefix u Flask blueprints pri montazhe na /synergy, chtoby puti sokhranilis.
- (Skrytyy #2) Podklyuchaem strogie security headers i OTel-instrumentirovanie bez pravok iskhodnykh routov.

ZEMNOY ABZATs:
Odin protsess Uvicorn obsluzhivaet i API, i “Shakhmatku”: sovmestimost putey ne lomaetsya, SSE rabotaet, metriki i zagolovki bezopasnosti - v komplekte.

# c=a+b"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware
from starlette.routing import Mount
from starlette.middleware.wsgi import WSGIMiddleware

# 1) Bazovyy FastAPI (suschestvuyuschiy API v2)
from asgi.synergy_api_v2 import app as api_v2  # drop-in import of an existing application
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# 2) Bezopasnye zagolovki i OTel-instrumentirovanie
try:
    from asgi.security_headers import SecurityHeaders
except Exception:
    SecurityHeaders = None  # type: ignore
try:
    from asgi.otel_instrumentation import instrument_app
except Exception:
    instrument_app = lambda app: app  # type: ignore

# 3) Flask application for CCE/Bordeaux
def _build_flask_app():
    from flask import Flask
    templates_dir = os.getenv("TEMPLATES_DIR", "templates")
    flask_app = Flask("ester_flask", template_folder=templates_dir)

    # Importiruem i registriruem blyuprinty bordy «bez prefiksa», t.k. montiruem na /synergy
    try:
        from routes.synergy_board_stream import register as reg_stream, bp as bp_stream  # type: ignore
        # Zaregistriruem blueprint s pereopredeleniem url_prefix=""
        flask_app.register_blueprint(bp_stream, url_prefix="")
    except Exception:
        # In older builds - via register()
        try:
            reg_stream(flask_app)  # type: ignore
        except Exception:
            pass

    # If there are separate HTML routes for the boards, connect
    try:
        from routes.synergy_board_routes import register as reg_board  # type: ignore
        reg_board(flask_app)
    except Exception:
        pass

    return flask_app

# 4) Finalnaya sborka
def build_app() -> FastAPI:
    app: FastAPI = api_v2  # we use the already created FastAPI as the core

    # COURSE is disabled by default; enable a soft profile if necessary
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # OTel i metriki
    try:
        app = instrument_app(app)  # type: ignore
    except Exception:
        pass

    # Security headers
    if SecurityHeaders is not None:
        app = SecurityHeaders(app)  # type: ignore

    # Montiruem Flask na /synergy: vnutri Flask blyuprinty zaregistrirovany bez prefiksa,
    # poetomu itogovye puti budut /synergy/board/stream, /synergy/board/aggregate i t.d.
    flask_app = _build_flask_app()
    app.mount("/synergy", WSGIMiddleware(flask_app))

    return app

# Export for Uvicorn
app = build_app()

# Allows you to launch the module directly: epothon -m asgi.app_mainyo
if __name__ == "__main__":
    import uvicorn  # type: ignore
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    workers = int(os.getenv("WORKERS", "1"))
    log_level = os.getenv("LOG_LEVEL", "info")
    uvicorn.run("asgi.app_main:app", host=host, port=port, log_level=log_level, workers=workers)