
# -*- coding: utf-8 -*-
"""
modules/thinking/auto_reg_thinking.py — myagkaya AUTO-REG tochka dlya myshleniya Ester.

Mosty:
- Yavnyy: (app.py ↔ novye adaptery) — edinaya tochka, cherez kotoruyu mozhno podklyuchit debug-marshruty.
- Skrytyy #1: (Flask-prilozhenie ↔ thinking_routes_alias) — bezopasnaya registratsiya blueprint'a.
- Skrytyy #2: (Politika A/B ↔ Diagnostika) — vklyuchenie cherez ENV-flag.

Ispolzovanie (ruchnoe, v app.py, v bloke AUTO-REG):
    from modules.thinking.auto_reg_thinking import auto_register as ester_thinking_auto_register
    ester_thinking_auto_register(app)

ENV:
    ESTER_THINK_DEBUG_AB = "A" | "B"
    A — po umolchaniyu: nichego ne registriruem.
    B — registriruem /ester/thinking-debug, esli Flask dostupen.

Zemnoy abzats:
Inzhener dobavlyaet odnu stroku v avto-registratsiyu, poluchaet prozrachnuyu diagnostiku
myshleniya bez vmeshatelstva v osnovnoy kod.
# c=a+b
"""
from __future__ import annotations

import os
from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from routes import thinking_routes_alias
except Exception:  # pragma: no cover
    thinking_routes_alias = None  # type: ignore


def _debug_enabled() -> bool:
    mode = (os.environ.get("ESTER_THINK_DEBUG_AB", "A") or "A").strip().upper()
    return mode == "B"


def auto_register(app: Any) -> None:
    """
    Bezopasnaya registratsiya thinking-debug blueprint.

    Pravila:
    - Ne padaet, esli Flask ili aliasy nedostupny.
    - Registratsiya tolko pri ESTER_THINK_DEBUG_AB=B.
    - Ne dubliruet blueprint, esli uzhe zaregistrirovan.
    """
    if not _debug_enabled():
        return

    if not app or not hasattr(app, "register_blueprint"):
        return

    if getattr(app, "blueprints", None) and "thinking_debug_bp" in app.blueprints:
        return

    if not thinking_routes_alias or not hasattr(thinking_routes_alias, "create_blueprint"):
        return

    try:
        bp = thinking_routes_alias.create_blueprint()
        if bp is None:
            return
        app.register_blueprint(bp)
    except Exception:
        # Nikakikh padeniy prilozheniya iz-za diagnostiki.
        return