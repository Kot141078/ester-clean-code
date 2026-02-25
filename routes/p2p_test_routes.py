# -*- coding: utf-8 -*-
from __future__ import annotations

"""routes/p2p_test_routes.py - testovyy P2P-rout: /p2p/echo

Name:
  Prostoy echo pod P2P-gardami ingress: vozvraschaet {"ok":true,"path":...}.
  Ispolzuetsya dlya bystroy proverki setevogo sloya i proksi.

Mosty:
- Yavnyy: (P2P ↔ Web) minimalnyy kontrakt zhivosti uzla.
- Skrytyy #1: (Inzheneriya ↔ Diagnostika) daet predskazuemyy otvet dlya healthcheck.
- Skrytyy #2: (Prozrachnost ↔ Zhurnaly) easy podklyuchit audit cherez middleware.

Zemnoy abzats:
Eto "stetoskop" dlya seti: prislali zapros - uslyshali ekho, znachit kanaly otkryty.

# c=a+b"""

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("p2p_test", __name__, url_prefix="/p2p")


@bp.get("/echo")
def p2p_echo():
    """Simple echo under P2P guards: returns ok=three and path metadata."""
    return jsonify({"ok": True, "path": request.path})


def register_p2p_test_routes(app) -> None:  # pragma: no cover
    """Compatible blueprint registration (historical name)."""
    app.register_blueprint(bp)


# Unified project hooks
def register(app) -> None:  # pragma: no cover
    app.register_blueprint(bp)


def init_app(app) -> None:  # pragma: no cover
    app.register_blueprint(bp)


__all__ = ["bp", "register_p2p_test_routes", "register", "init_app"]
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app