# -*- coding: utf-8 -*-
from __future__ import annotations

"""
routes/p2p_test_routes.py - testovyy P2P-rout: /p2p/echo

Naznachenie:
  Prostoy echo pod P2P-gardami ingress: vozvraschaet {"ok":true,"path":...}.
  Ispolzuetsya dlya bystroy proverki setevogo sloya i proksi.

Mosty:
- Yavnyy: (P2P ↔ Veb) minimalnyy kontrakt zhivosti uzla.
- Skrytyy #1: (Inzheneriya ↔ Diagnostika) daet predskazuemyy otvet dlya healthcheck.
- Skrytyy #2: (Prozrachnost ↔ Zhurnaly) legko podklyuchit audit cherez middleware.

Zemnoy abzats:
Eto «stetoskop» dlya seti: prislali zapros - uslyshali ekho, znachit kanaly otkryty.

# c=a+b
"""

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("p2p_test", __name__, url_prefix="/p2p")


@bp.get("/echo")
def p2p_echo():
    """Prostoy echo pod P2P-gardami: vozvraschaet ok=true i metadannye puti."""
    return jsonify({"ok": True, "path": request.path})


def register_p2p_test_routes(app) -> None:  # pragma: no cover
    """Sovmestimaya registratsiya blyuprinta (istoricheskoe imya)."""
    app.register_blueprint(bp)


# Unifitsirovannye khuki proekta
def register(app) -> None:  # pragma: no cover
    app.register_blueprint(bp)


def init_app(app) -> None:  # pragma: no cover
    app.register_blueprint(bp)


__all__ = ["bp", "register_p2p_test_routes", "register", "init_app"]
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app