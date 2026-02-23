# -*- coding: utf-8 -*-
"""
routes/telegram_control_ui_routes.py - HTML-panel upravleniya (tolko UI).

Prefiks: /tg/ctrl
Marshruty:
  • GET /tg/ctrl/ui  - HTML-stranitsa (templates/telegram_control_ui.html)

JSON-API vynesen v routes/telegram_control_routes.py (prefiks /tg/ctrl/api),
chtoby ne bylo dvoynoy registratsii odnikh i tekh zhe endpointov.

Zemnoy abzats (inzheneriya):
UI otdelen ot API - bezopasnee provodit izmeneniya v shablone, ne zatragivaya marshruty JSON.

Mosty:
- Yavnyy (Kibernetika ↔ Arkhitektura): operatorskiy pult «poverkh» stabilnogo API.
- Skrytyy 1 (Infoteoriya ↔ Interfeysy): nezavisimye sloi predstavleniya i dannykh.
- Skrytyy 2 (Anatomiya ↔ PO): kak kora i talamus - raznye sloi, edinaya funktsiya.

# c=a+b
"""
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("telegram_control_ui", __name__, url_prefix="/tg/ctrl")


@bp.get("/ui")
def ui():
    """
    Stranitsa sama dergaet JSON-ruchki /tg/ctrl/api/* (JWT beretsya iz localStorage v brauzere).
    """
    return render_template("telegram_control_ui.html")


def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


__all__ = ["bp", "register", "init_app"]
# c=a+b