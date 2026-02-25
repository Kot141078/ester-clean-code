# -*- coding: utf-8 -*-
"""modules/ester/auto_reg_ester.py - AUTO-REG dlya statusnykh marshrutov Ester.

Mosty:
- Yavnyy: (app.py ↔ ester_status_routes_alias) - register /ester/status.
- Skrytyy #1: (ENV ↔ Diagnostika) — upravlyaetsya flagom ESTER_STATUS_AB.
- Skrytyy #2: (Stabilnost ↔ Prozrachnost) — ne vliyaet na osnovnoy API, tolko dobavlyaet read-only.

ENV:
    ESTER_STATUS_AB = "A" | "B"
    A - po umolchaniyu, ne registriruem status.
    B - register /ester/status i /ester/modes.

Zemnoy abzats:
Inzhener vklyuchaet ESTER_STATUS_AB=B i vidit rezhimy Ester odnim zaprosom.
# c=a+b"""
from __future__ import annotations

import os
from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from routes import ester_status_routes_alias
except Exception:  # pragma: no cover
    ester_status_routes_alias = None  # type: ignore


def _status_enabled() -> bool:
    return (os.getenv("ESTER_STATUS_AB", "A") or "A").strip().upper() == "B"


def auto_register(app: Any) -> None:
    if not _status_enabled():
        return
    if not app or not hasattr(app, "register_blueprint"):
        return
    if getattr(app, "blueprints", None) and "ester_status_bp" in app.blueprints:
        return
    if not ester_status_routes_alias or not hasattr(ester_status_routes_alias, "create_blueprint"):
        return
    try:
        bp = ester_status_routes_alias.create_blueprint()
        if bp is not None:
            app.register_blueprint(bp)
    except Exception:
        # Status should not break Esther.
        return