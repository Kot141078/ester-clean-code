# -*- coding: utf-8 -*-
"""routes.register_all

Aggregator for route registration.

Some parts of the codebase call routes.register_all.register(app) expecting it to
register UI endpoints too. Older versions imported non-existing symbols like
register_ui/register_manifest_ui from route modules; this file fixes that by
probing for multiple possible function names.
"""

from __future__ import annotations

import importlib
import logging
from types import ModuleType
from typing import Any, Optional, Sequence
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

LOG = logging.getLogger("routes.register_all")


def _optional_import(name: str) -> Optional[ModuleType]:
    try:
        return importlib.import_module(name)
    except Exception as e:
        LOG.info("[routes.register_all] optional import failed: %s: %s", name, e)
        return None


def _is_flask_like_app(app: Any) -> bool:
    return bool(app is not None and hasattr(app, "register_blueprint") and hasattr(app, "url_map"))


def _is_fastapi_like_app(app: Any) -> bool:
    return bool(app is not None and hasattr(app, "include_router") and hasattr(app, "router"))


def _call_first(module: ModuleType, app: Any, names: Sequence[str]) -> bool:
    for n in names:
        fn = getattr(module, n, None)
        if callable(fn):
            try:
                fn(app)
                LOG.info("[routes.register_all] %s.%s OK", module.__name__, n)
                return True
            except Exception as e:
                LOG.warning("[routes.register_all] %s.%s failed: %s", module.__name__, n, e)
                return False
    return False


def register(app: Any) -> Any:
    if _is_fastapi_like_app(app):
        LOG.warning("[routes.register_all] FastAPI app detected; skip Flask route registration")
        return app
    if not _is_flask_like_app(app):
        LOG.warning("[routes.register_all] Unsupported app type for Flask registration: %s", type(app).__name__)
        return app

    modules = [
        "routes.health_routes",
        "routes.docs_routes",
        "routes.memory_routes",
        "routes.telegram_routes",
        "routes.whatsapp_routes",
        "routes.chat_api_routes",
        "routes.admin_routes",
        "routes.telemetry_routes",
        "routes.tools_routes",
        "routes.file_routes",
        "routes.mission_routes",
        "routes.docs_ui_routes",
        "routes.mvp_manifest_routes",
        "routes.mvp_autonomy_routes",
        "routes.admin_portable_firststart",
        "routes.admin_portable_links",
        "routes.admin_portable_metrics",
        "routes.admin_portable_files",
        "routes.admin_identity",
        "routes.admin_settings_ui",
        "routes.admin_vault_keys",
    ]

    fn_names = (
        # new & old naming variants
        "register",
        "register_ui",
        "register_manifest_ui",
        "register_blueprints",
        "register_routes",
        "register_api",
        "init_app",
        "setup",
    )

    for modname in modules:
        m = _optional_import(modname)
        if not m:
            continue
        called = _call_first(m, app, fn_names)
        if not called:
            # Quietly ignore: module may only export a Blueprint object.
            pass

    return app


# Backward-compatible aliases some code expects
def register_ui(app: Any) -> Any:
    return register(app)


def register_manifest_ui(app: Any) -> Any:
    return register(app)
