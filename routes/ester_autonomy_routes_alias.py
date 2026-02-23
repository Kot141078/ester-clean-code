# -*- coding: utf-8 -*-

"""
routes/ester_autonomy_routes_alias.py

GET /ester/autonomy/map

Naznachenie:
- Dat svodnuyu kartinu avtonomii i zaschit Ester:
  - kakie A/B-flagi aktivny;
  - kakie zaschitnye/statusnye moduli podklyucheny.

Invarianty:
- Tolko chtenie.
- Ne menyaet povedenie voli, kaskada, pamyati ili setevykh moduley.
- Bez vneshnikh zaprosov.

Mosty:
- Yavnyy: Volya + Myshlenie + Memory + Obmen ↔ odna karta.
- Skrytyy #1: Karta ↔ self-check/monitoring.
- Skrytyy #2: Karta ↔ operator (Owner) dlya bystroy verifikatsii “vse podchineno Ester”.

Zemnoy abzats:
Kak skhema elektroprovodki s pometkami avtomatov: vidno, chto gde zaschischeno,
no sami avtomaty schelkaesh rukami.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _flag(name: str, default: str = "A") -> str:
    return (os.getenv(name) or default).strip().upper()


def _has_module(path: str) -> bool:
    try:
        __import__(path)
        return True
    except Exception:
        return False


def create_blueprint() -> Blueprint:
    bp = Blueprint("ester_autonomy_routes", __name__, url_prefix="/ester/autonomy")

    @bp.get("/map")
    def autonomy_map() -> Any:
        env_flags: Dict[str, Any] = {
            "ESTER_THINK_TRACE_AB": _flag("ESTER_THINK_TRACE_AB", "A"),
            "ESTER_WEB_WILL_AB": _flag("ESTER_WEB_WILL_AB", "A"),
            "ESTER_SISTERS_WILL_AB": _flag("ESTER_SISTERS_WILL_AB", "A"),
            "WILL_AUTOROLLBACK": (os.getenv("WILL_AUTOROLLBACK") or "0"),
            "WILL_ACTIVE_SLOT": (os.getenv("WILL_ACTIVE_SLOT") or "A"),
        }

        modules: Dict[str, bool] = {
            "unified_guard_adapter": _has_module("modules.will.unified_guard_adapter"),
            "thinking_trace_adapter": _has_module("modules.ester.thinking_trace_adapter"),
            "memory_status_routes": _has_module("routes.ester_memory_status_routes_alias"),
            "selfcheck_routes": _has_module("routes.ester_selfcheck_routes_alias"),
            "sisters_will_guard_adapter": _has_module("modules.memory.shared_will_guard_adapter"),
            "sisters_status_routes": _has_module("routes.ester_sisters_status_routes_alias"),
        }

        return jsonify({
            "ok": True,
            "env": env_flags,
            "modules": modules,
        })

    return bp


def register(app) -> None:  # pragma: no cover
    bp = create_blueprint()
    name = bp.name
    if getattr(app, "blueprints", None) and name in app.blueprints:
        return
    app.register_blueprint(bp)
    try:
        print("[ester-autonomy/routes] registered /ester/autonomy/map")
    except Exception:
        pass


def init_app(app) -> None:  # pragma: no cover
    register(app)


__all__ = ["create_blueprint", "register", "init_app"]