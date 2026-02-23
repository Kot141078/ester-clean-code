# -*- coding: utf-8 -*-
"""
wsgi_secure.py — prodakshn-entripoint «Ester».
Funktsii:
  - create_app(): Flask app so vklyuchennymi bezopasnymi nastroykami
Osobennosti:
  * CORS (prostoy after_request, bez vneshnikh zavisimostey)
  * JSON-logirovanie zaprosov/otvetov s correlation id (X-Request-Id)
  * ProxyFix podderzhka (esli vklyucheno cherez ENV USE_PROXY_FIX=1)
  * JWT HS256/RS256 (ENV: JWT_ALG=HS256|RS256, JWT_SECRET | JWT_PRIVATE_KEY_PATH/JWT_PUBLIC_KEY_PATH)
  * RBAC: security/rbac.attach_app(app) — deny po /ops/* i /replication/* dlya user
  * Routy registriruyutsya myagko (try/except) — drop-in sovmestimost
  * VAZhNO: ranniy import modules.mm_compat.patch_memory_manager() dlya vyravnivaniya API .cards

Zapusk:
  gunicorn -w 4 -b 0.0.0.0:8080 wsgi_secure:app
ili
  python wsgi_secure.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict

from flask import Flask, g, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token  # type: ignore
from werkzeug.middleware.proxy_fix import ProxyFix  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BUILD_TS = os.getenv("ESTER_BUILD_TS", str(int(time.time())))


def _load_jwt_keys(app: Flask) -> None:
    alg = (os.getenv("JWT_ALG") or "HS256").upper()
    app.config["JWT_ALGORITHM"] = alg
    if alg == "RS256":
        priv_path = os.getenv("JWT_PRIVATE_KEY_PATH")
        pub_path = os.getenv("JWT_PUBLIC_KEY_PATH")
        if not (priv_path and pub_path and os.path.exists(priv_path) and os.path.exists(pub_path)):
            raise RuntimeError(
                "RS256 vybran, no klyuchi ne naydeny (JWT_PRIVATE_KEY_PATH/JWT_PUBLIC_KEY_PATH)"
            )
        app.config["JWT_PRIVATE_KEY"] = open(priv_path, "r", encoding="utf-8").read()
        app.config["JWT_PUBLIC_KEY"] = open(pub_path, "r", encoding="utf-8").read()
    else:
        app.config["JWT_SECRET_KEY"] = os.getenv(
            "JWT_SECRET", "devsecret"
        )  # HS256 po umolchaniyu


def _setup_logging(app: Flask) -> None:
    logger = logging.getLogger("ester")
    logger.setLevel(logging.INFO)
    h = logging.StreamHandler(sys.stdout)
    logger.addHandler(h)
    app.logger.handlers = []  # izbegaem dublirovaniya
    app.logger.propagate = True

    @app.before_request
    def _begin():
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        g.request_id = rid
        g.t0 = time.time()

    @app.after_request
    def _after(resp):
        try:
            payload = {
                "ts": int(time.time()),
                "rid": getattr(g, "request_id", ""),
                "ip": request.headers.get("X-Forwarded-For") or request.remote_addr,
                "method": request.method,
                "path": request.path,
                "status": resp.status_code,
                "dur_ms": int((time.time() - getattr(g, "t0", time.time())) * 1000),
            }
            logging.getLogger("ester").info(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass
        # CORS
        allow = os.getenv("CORS_ALLOW_ORIGINS", "*")
        resp.headers.setdefault("Access-Control-Allow-Origin", allow)
        resp.headers.setdefault(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, X-CSRF-Token, X-Request-Id",
        )
        resp.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        resp.headers.setdefault("X-Request-Id", getattr(g, "request_id", ""))
        return resp


def _register_routes(app: Flask) -> None:
    # Bazovye
    try:
        from routes.root_routes import register_root_routes  # type: ignore

        register_root_routes(app)
    except Exception:
        pass
    # Providers / Chat / Ingest / i dr.
    for mod, fn in [
        ("routes.providers_routes", "register_providers_routes"),
        ("routes.chat_routes", "register_chat_routes"),
        ("routes.ingest_routes", "register_ingest_routes"),
        ("routes.replication_routes", "register_replication_routes"),
        ("routes.backup_routes", "register_backup_routes"),
        ("routes.research_routes", "register_research_routes"),
        ("routes.empathy_routes", "register_empathy_routes"),
        ("routes.events_routes", "register_events_routes"),
        ("routes.mem_kg_routes", "register_mem_kg_routes"),
        ("routes.telegram_feed", "register_telegram_feed_routes"),
        ("routes.share_bridge_routes", "register_share_bridge_routes"),
        ("routes.session_guardian_routes", "register_session_guardian_routes"),
        ("routes.forms_routes", "register_forms_routes"),
        ("routes.feed_routes", "register_feed_routes"),
    ]:
        try:
            m = __import__(mod, fromlist=[fn])
            getattr(m, fn)(app)
        except Exception:
            continue


def _simple_auth(app: Flask) -> None:
    """
    Optsionalnaya prostaya autentifikatsiya (dlya lokalnoy razrabotki).
    Vklyuchaetsya ENV ENABLE_SIMPLE_LOGIN=1.
    POST /auth/login {"user":"owner","role":"admin|user"} -> {"access_token": "..."}
    """
    if os.getenv("ENABLE_SIMPLE_LOGIN", "0") != "1":
        return

    @app.post("/auth/login")
    def login():
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        user = (data.get("user") or "user").strip()
        role = (data.get("role") or "user").strip()
        add = {"roles": [role], "user": user}
        token = create_access_token(identity=user, additional_claims=add)
        return jsonify({"access_token": token, "user": user, "role": role})


def create_app() -> Flask:
    # Ranniy patch sovmestimosti MemoryManager.cards
    try:
        from modules.mm_compat import patch_memory_manager  # type: ignore

        patch_memory_manager()
    except Exception:
        pass

    app = Flask(__name__, static_folder="static", template_folder="templates")
    _load_jwt_keys(app)
    JWTManager(app)
    if os.getenv("USE_PROXY_FIX", "1") == "1":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)  # type: ignore
    _setup_logging(app)
    _register_routes(app)
    _simple_auth(app)
    # RBAC attach (geyt na /ops/* i /replication/*; nastraivaemo cherez ENV)
    try:
        from security.rbac import attach_app  # type: ignore

        attach_app(app)
    except Exception:
        pass
    return app


app = create_app()

if __name__ == "__main__":
    # Po umolchaniyu Ester slushaet 8090 (kak v tvoikh skriptakh zapuska). Mozhno pereopredelit ENV PORT.
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8090"))
    debug = os.getenv("DEBUG", "0") == "1"

    # Vstroennyy server Flask — tolko dlya dev/testa. Dlya prodakshena ispolzuy gunicorn/uwsgi.
    app.run(host=host, port=port, debug=debug)