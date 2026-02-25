# -*- coding: utf-8 -*-
"""routes/telegram_control_ui_routes.py - HTML-panel upravleniya (only UI).

Prefixes: /tg/ctrl
Route:
  • GET /tg/ctrl/ui - HTML-stranitsa (templates/telegram_control_ui.html)

JSON-API vynesen v routes/telegram_control_routes.py (prefiks /tg/ctrl/api),
chtoby ne bylo dvoynoy registratsii odnikh i tekh zhe endpointov.

Zemnoy abzats (inzheneriya):
UI otdelen ot API - bezopasnee provodit izmeneniya v shablone, ne zatragivaya route JSON.

Mosty:
- Yavnyy (Kibernetika ↔ Arkhitektura): operatorskiy remote “poverkh” stabilnogo API.
- Skrytyy 1 (Infoteoriya ↔ Interfeysy): nezavisimye sloi predstavleniya i dannykh.
- Skrytyy 2 (Anatomiya ↔ PO): kak kora i talamus - raznye sloi, edinaya funktsiya.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("telegram_control_ui", __name__, url_prefix="/tg/ctrl")


@bp.get("/ui")
def ui():
    """The page itself pulls the ZhSON handles /tg/strl/api/* (ZhVT is taken from the localStorage in the browser)."""
    return render_template("telegram_control_ui.html")


def register(app):  # pragma: no cover
    """Drop-in registration of blueprint (project contract)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


__all__ = ["bp", "register", "init_app"]
# c=a+b