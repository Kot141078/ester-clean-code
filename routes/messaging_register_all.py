# -*- coding: utf-8 -*-
"""routes.messaging_register_all

Registers messaging-related blueprints (Telegram / WhatsApp) in a defensive way.

Typical failure we fix:
- telegram_routes exists but exports blueprint as `bp` while caller expects `telegram_bp`
- whatsapp_routes may not exist in some installs

This file tries multiple names and never raises.
"""

from __future__ import annotations

import importlib
import logging
from types import ModuleType
from typing import Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

LOG = logging.getLogger("routes.messaging_register_all")


def _optional_import(name: str) -> Optional[ModuleType]:
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def _find_blueprint(module: ModuleType, preferred_names):
    for n in preferred_names:
        bp = getattr(module, n, None)
        if bp is not None:
            return bp
    # fallback: first attribute that looks like a flask Blueprint (duck-typing)
    for _, v in vars(module).items():
        if hasattr(v, "route") and hasattr(v, "name"):
            return v
    return None


def _register_blueprint_once(app: Any, bp: Any, label: str) -> bool:
    bp_name = str(getattr(bp, "name", "") or "").strip()
    existing = set(getattr(app, "blueprints", {}).keys())
    if bp_name and bp_name in existing:
        LOG.info("[messaging_register_all] %s blueprint already registered: %s", label, bp_name)
        return False
    try:
        app.register_blueprint(bp)  # type: ignore[attr-defined]
        LOG.info("[messaging_register_all] %s blueprint registered", label)
        return True
    except Exception as e:
        # Idempotent path: duplicate registration is not an availability problem.
        if "already registered" in str(e).lower():
            LOG.info(
                "[messaging_register_all] %s blueprint already registered: %s",
                label,
                (bp_name or "<unknown>"),
            )
            return False
        raise


def register(app: Any) -> Any:
    # Telegram
    try:
        m = _optional_import("routes.telegram_routes")
        if not m:
            raise ImportError("routes.telegram_routes not found")
        bp = _find_blueprint(m, ["telegram_bp", "bp", "telegram_blueprint", "blueprint"])
        if bp is None:
            raise ImportError("no blueprint object exported")
        _register_blueprint_once(app, bp, "Telegram")
    except Exception as e:
        LOG.warning("[messaging_register_all] Telegram routes not available: %s", e)

    # WhatsApp (two possible layouts)
    try:
        m = _optional_import("routes.whatsapp_routes")
        if not m:
            # legacy
            m = _optional_import("routes.whatsapp_webhook_routes")
        if not m:
            raise ImportError("whatsapp routes module not found")
        bp = _find_blueprint(m, ["whatsapp_bp", "bp", "whatsapp_blueprint", "webhook_bp", "blueprint"])
        if bp is None:
            raise ImportError("no blueprint object exported")
        _register_blueprint_once(app, bp, "WhatsApp")
    except Exception as e:
        LOG.warning("[messaging_register_all] WhatsApp routes not available: %s", e)

    return app
