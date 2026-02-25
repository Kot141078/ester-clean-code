# -*- coding: utf-8 -*-
"""routes/register_ui.py - agregator UI-blyuprintov (komplementaren k app._register_routes i register_all.py).

Modul otvechaet za registratsiyu spetsifichnykh dlya UI routes (blueprints),
garantiruya ikh dobavlenie tolko v tom sluchae, esli oni esche ne suschestvuyut v prilozhenii.

Istoricheskaya reference:
Ranee etot modul sluzhil sloem sovmestimosti dlya ustarevshikh vyzovov v app.py,
perenapravlyaya vyzov `register_all_ui` na `register_all_routes`. This obespechivalo
odinakovyy rezultat pri raznykh putyakh initsializatsii i vystupalo mostom mezhdu
arkhitekturoy i sovmestimostyu.

Tekuschaya realizatsiya:
Teper modul vypolnyaet tochechnuyu registratsiyu UI-marshrutov, proveryaya nalichie
exactly sovpadeniya pravila pered dobavleniem.

Puti, kotorye dobavlyayutsya pri otsutstvii (TOChNOE sovpadenie pravila!):
  • /chat/telegram (routes.telegram_feed_ui_routes.bp)
  • /tg/ctrl/ui (routes.telegram_control_ui_routes.bp)
  • /routes_index.html (routes.routes_index.bp_routes_index)

Mosty:
- Yavnyy: (UI ↔ Web-server) bezopasnaya tochechnaya registratsiya UI-marshrutov bez dublirovaniya.
- Skrytyy #1: (Sovmestimost ↔ Arkhitektura) modul abstract razlichiya putey initsializatsii.
- Skrytyy #2: (Logika ↔ Kontrakty) strogaya proverka tochnogo sovpadeniya URL-pravil isklyuchaet lozhnye srabatyvaniya.

Zemnoy abzats:
Dumay o module kak o “patch-paneli” v stoyke: soedinyaem tolko nuzhnye porty i ne tseplyaemsya za pokhozhie,
isklyuchaya sluchaynye petli. Registriruem UI, esli v karte routes net tochnogo sovpadeniya - i vse rabotaet prozrachno.

# c=a+b"""
from __future__ import annotations

from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _have_exact_rule(app, rule_exact: str) -> bool:
    """Checks the presence of the exact rule (URL rule) in the application.
    The comparison takes place without taking into account the trailing slash."""
    try:
        want = rule_exact.rstrip("/")
        for r in app.url_map.iter_rules():  # type: ignore[attr-defined]
            if str(r.rule).rstrip("/") == want:
                return True
        return False
    except Exception:
        return False


def register_all_ui(app) -> None:
    """Registers UI blueprints if corresponding routes are missing."""
    # /chat/telegram
    if not _have_exact_rule(app, "/chat/telegram"):
        try:
            from routes.telegram_feed_ui_routes import bp as bp_feed  # type: ignore
            app.register_blueprint(bp_feed)
        except Exception:
            # Protects the main thread - UI is optional.
            pass

    # /tg/ctrl/ui
    if not _have_exact_rule(app, "/tg/ctrl/ui"):
        try:
            from routes.telegram_control_ui_routes import bp as bp_ctrl  # type: ignore
            app.register_blueprint(bp_ctrl)
        except Exception:
            pass

    # /routes_index.html
    if not _have_exact_rule(app, "/routes_index.html"):
        try:
            from routes.routes_index import bp_routes_index  # type: ignore
            app.register_blueprint(bp_routes_index)
        except Exception:
            pass


__all__ = ["register_all_ui"]
# c=a+b


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
# stub for register_oh: no power supply/router/register_*_rutes yet
def register(app):
    return True

# === /AUTOSHIM ===