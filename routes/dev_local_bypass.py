# -*- coding: utf-8 -*-
"""
routes/dev_local_bypass.py - lokalnyy «admin-propusk» dlya razrabotki.

Mosty:
- Yavnyy: (Ekspluatatsiya ↔ Bezopasnost) - bezopasnyy obkhod tolko na 127.0.0.1.
- Skrytyy #1: (Kibernetika ↔ Refleksy) - vklyuchaetsya/vyklyuchaetsya ENV bez pravok koda.
- Skrytyy #2: (Infoteoriya ↔ Diagnostika) - yavnyy /ui/ping dlya proverki konteksta.

Zemnoy abzats:
Esli zapros s 127.0.0.1 i LOCAL_DEV_BYPASS=1 - stavim g.is_admin=True i g.user_roles=['admin']
PERED lyubymi guard'ami. Togda auth_rbac uvidit «admin» i perestanet otdavat 403.

# c=a+b
"""
from __future__ import annotations

import os
import re
from typing import Optional

from flask import Blueprint, g, jsonify, request  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("dev_local_bypass", __name__)

def _is_true(val: Optional[str]) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")

def _remote_ip() -> str:
    xff = (request.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return (request.remote_addr or "").strip()

def _install_early_bypass(app):
    def _early_local_admin_bypass():
        try:
            if not _is_true(os.getenv("LOCAL_DEV_BYPASS", "0")):
                return
            ip = _remote_ip()
            pattern = os.getenv("DEV_BYPASS_REMOTE_ADDR_REGEX", r"^127\.0\.0\.1$")
            if not re.match(pattern, ip):
                return
            if not hasattr(g, "user"):
                g.user = "local-dev"
            g.user_roles = ["admin"]
            g.is_admin = True
            request.environ["ESTER_LOCAL_DEV"] = "1"
        except Exception:
            return
    app.before_request_funcs.setdefault(None, [])
    app.before_request_funcs[None].insert(0, _early_local_admin_bypass)

@bp.get("/ui/ping")
def ui_ping():
    return jsonify({
        "ok": True,
        "user": getattr(g, "user", None),
        "roles": getattr(g, "user_roles", None),
        "is_admin": getattr(g, "is_admin", False),
        "remote": _remote_ip(),
        "dev_bypass": bool(request.environ.get("ESTER_LOCAL_DEV")),
    })

def register_routes(app):
    app.register_blueprint(bp)
    _install_early_bypass(app)

# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app