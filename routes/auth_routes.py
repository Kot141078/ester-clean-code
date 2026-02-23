# -*- coding: utf-8 -*-
# routes/auth_routes.py
"""
routes/auth_routes.py - bazovaya stranitsa /auth/ui (ssylki na avto-JWT i prostuyu formu logina).

Puti:
  • GET /auth/ui - HTML s kratkimi podskazkami; ne vmeshivaetsya v uzhe suschestvuyuschie endpointy.

Zemnoy abzats (inzhiniring):
Eto «tablichka u vkhoda»: ssylki na sposoby polucheniya tokena bez kopaniya v dokumentatsii.

Mosty:
- Yavnyy (Kibernetika ↔ Arkhitektura): operator nakhodit dorozhku k autentifikatsii.
- Skrytyy 1 (Infoteoriya ↔ Interfeysy): umenshenie kognitivnoy nagruzki za schet edinoy tochki vkhoda.
- Skrytyy 2 (Anatomiya ↔ PO): kak ukazatelnyy palets - pokazyvaet, kuda nazhat.
"""
from __future__ import annotations

from flask import Blueprint, render_template_string
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("auth_routes", __name__, url_prefix="/auth")

HTML = """<!doctype html>
<meta charset="utf-8"/>
<title>Auth UI</title>
<style>
body{font:16px/1.4 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;padding:24px}
a{color:inherit}
h1{margin:0 0 12px 0}
ul{margin:0;padding-left:18px}
</style>
<h1>Autentifikatsiya</h1>
<ul>
  <li><a href="/auth/auto">Vydat JWT po imeni</a> - bystroe poluchenie tokena (naprimer: Owner → admin).</li>
  <li><a href="/tg/ctrl/ui">Panel Telegram-bota</a> - upravlenie imenem/opisaniem/komandami (nuzhen JWT).</li>
  <li><a href="/chat/telegram">Lenta Telegram</a> - nablyudat i otvechat (JWT dlya otpravki).</li>
</ul>
"""

@bp.get("/ui")
def ui():
    # Vozvraschaem prostuyu podskazku po dostupnym auth-deystviyam
    return render_template_string(HTML)


def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta po kontraktu proekta."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


__all__ = ["bp", "register", "init_app"]

# c=a+b