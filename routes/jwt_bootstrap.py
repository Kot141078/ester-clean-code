# -*- coding: utf-8 -*-
"""
routes.jwt_bootstrap

Minimalnyy butstrap JWT dlya zaschischennykh ruchek (napr. /providers/select),
chtoby ubrat 500 KeyError: 'JWT_TOKEN_LOCATION' i ne trogat suschestvuyuschiy app.py.
Podklyuchaetsya kak obychnyy Blueprint i initsializiruet Flask-JWT-Extended.

A/B-slot: ESTER_JWT_BOOTSTRAP_AB (A|B). Pri oshibke bezopasno logiruem i ne lomaem server.
YaVNYY MOST: UI/portal → (Authorization: Bearer) → /providers/* (JWT guard) → provaydery.
SKRYTYE MOSTY: (1) localStorage.jwt ↔ zagolovok Authorization; (2) env → app.config.
Zemnoy abzats: predstavte elektricheskiy zhgut pod kapotom — my prosto «schelknuli» kolodku
pitaniya na blok okhrany (JWT), chtoby starye knopki na paneli snova zamykali tsep.
c=a+b
"""
from __future__ import annotations

import os
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from flask_jwt_extended import JWTManager
except Exception:  # pragma: no cover
    JWTManager = None  # type: ignore

bp = Blueprint("jwt_bootstrap", __name__, url_prefix="/_jwt")

def _resolve_jwt_secret() -> str:
    secret = (os.environ.get("ESTER_JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or "").strip()
    if secret:
        return secret
    if os.environ.get("ESTER_DEV_MODE", "0").strip() == "1":
        return os.urandom(32).hex()
    return ""

def _init_jwt(app) -> dict:
    info = {"initialized": False, "note": ""}
    if JWTManager is None:
        info["note"] = "flask_jwt_extended ne ustanovlen; JWT propuschen"
        return info

    secret = _resolve_jwt_secret()
    if secret:
        app.config.setdefault("JWT_SECRET_KEY", secret)
    app.config.setdefault("JWT_TOKEN_LOCATION", ["headers", "query_string"])
    app.config.setdefault("JWT_HEADER_NAME", "Authorization")
    app.config.setdefault("JWT_HEADER_TYPE", "Bearer")
    app.config.setdefault("JWT_COOKIE_SECURE", False)
    app.config.setdefault("JWT_COOKIE_CSRF_PROTECT", False)

    try:
        JWTManager(app)
        info["initialized"] = True
        info["note"] = "JWTManager(app) ok"
    except Exception as e:  # pragma: no cover
        info["note"] = f"JWT init warn: {e!r}"
    return info

@bp.record_once
def _on_register(setup_state):
    app = setup_state.app
    ab = os.environ.get("ESTER_JWT_BOOTSTRAP_AB", "A").upper()
    try:
        if ab not in ("A", "B"):
            ab = "A"
        if ab == "A":
            info = _init_jwt(app)
            app.logger.info("JWT bootstrap(A): %s", info)
        else:
            app.logger.info("JWT bootstrap(B): propuscheno po AB-pereklyuchatelyu")
    except Exception as e:  # strakhovka
        try:
            app.logger.exception("JWT bootstrap: fatal %r — propuskayu", e)
        except Exception:
            pass

@bp.get("/status")
def jwt_status():
    from flask import current_app
    cfg = current_app.config
    keys = ["JWT_TOKEN_LOCATION", "JWT_HEADER_NAME", "JWT_HEADER_TYPE"]
    snapshot = {k: cfg.get(k) for k in keys}
    snapshot["has_secret"] = bool(cfg.get("JWT_SECRET_KEY"))
    return jsonify(ok=True, ab=os.environ.get("ESTER_JWT_BOOTSTRAP_AB", "A"), **snapshot)

def register(app):
    app.register_blueprint(bp)
    return app
