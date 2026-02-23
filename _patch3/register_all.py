# -*- coding: utf-8 -*-
"""Ester project: centralized registration entrypoints.

This file is intentionally defensive:
- It should never crash the app if optional modules are missing.
- It provides stable symbols expected by run_ester_fixed.py and others:
    * register_all(app)
    * register(app)              (alias)
    * register_all_skills(skill_manager)

Common failure mode this fixes:
- Multiple register_all.py files exist (root / modules / routes) and the root one
  may not expose register_all_skills(), causing ImportError.

Keep this module small and predictable: do orchestration here, and keep actual
route/skill code inside their packages.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import os
import pkgutil
from types import ModuleType
from typing import Any, Callable, Iterable, Optional, Sequence, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    # Optional dependency; required only if blueprint scanning is used.
    from flask import Blueprint  # type: ignore
except Exception:  # pragma: no cover
    Blueprint = object  # type: ignore


LOG = logging.getLogger("register_all")


def _env_truthy(name: str, default: str = "0") -> bool:
    v = os.getenv(name, default)
    return str(v).strip().lower() in {"1", "true", "yes", "on", "y"}


def _optional_import(module_name: str) -> Optional[ModuleType]:
    try:
        return importlib.import_module(module_name)
    except Exception as e:
        LOG.info("[register_all] Optional import failed: %s: %s", module_name, e)
        return None


def _call_first_available(module: ModuleType, app: Any, fn_names: Sequence[str]) -> bool:
    """Call first existing callable from fn_names. Returns True if something was called."""
    for fn in fn_names:
        obj = getattr(module, fn, None)
        if callable(obj):
            try:
                obj(app)
                LOG.info("[register_all] %s.%s OK", module.__name__, fn)
                return True
            except Exception as e:
                LOG.warning("[register_all] %s.%s failed: %s", module.__name__, fn, e)
                return False
    return False


def _scan_and_register_blueprints(app: Any, package_name: str = "routes") -> None:
    """Best-effort scan of a package to auto-register Blueprint objects."""
    pkg = _optional_import(package_name)
    if not pkg or not hasattr(pkg, "__path__"):
        return

    registered = 0
    for modinfo in pkgutil.iter_modules(pkg.__path__, package_name + "."):
        m = _optional_import(modinfo.name)
        if not m:
            continue
        for _, obj in inspect.getmembers(m):
            try:
                is_bp = isinstance(obj, Blueprint)  # type: ignore[arg-type]
            except Exception:
                is_bp = False
            if not is_bp:
                continue

            # Avoid duplicates by blueprint name
            bp_name = getattr(obj, "name", None)
            if not bp_name:
                continue
            if hasattr(app, "blueprints") and bp_name in getattr(app, "blueprints", {}):
                continue
            try:
                app.register_blueprint(obj)  # type: ignore[attr-defined]
                registered += 1
                LOG.info("[register_all] Blueprint registered: %s (%s)", bp_name, m.__name__)
            except Exception as e:
                LOG.warning("[register_all] Blueprint failed: %s (%s): %s", bp_name, m.__name__, e)

    if registered:
        LOG.info("[register_all] Blueprint scan registered %d blueprints", registered)


def _attach_cors_if_enabled(app: Any) -> None:
    # Default OFF, because this is a local box by design.
    if not _env_truthy("ESTER_ENABLE_CORS", "0"):
        LOG.info("[register_all] CORS disabled by env")
        return
    try:
        from flask_cors import CORS  # type: ignore
        CORS(app)
        LOG.info("[register_all] CORS enabled")
    except Exception as e:
        LOG.warning("[register_all] CORS requested but flask_cors not available: %s", e)


def _attach_hub_if_available(app: Any) -> None:
    # Hub is optional; some deployments do not ship it.
    for modname in ("hub", "modules.hub"):
        m = _optional_import(modname)
        if not m:
            continue
        fn = getattr(m, "create_hub", None)
        if callable(fn):
            try:
                hub = fn(app)  # type: ignore[misc]
                # store reference (if app supports it)
                if hasattr(app, "config") and isinstance(getattr(app, "config"), dict):
                    app.config["ESTER_HUB"] = hub
                LOG.info("[register_all] Hub attached via %s.create_hub", modname)
                return
            except Exception as e:
                LOG.warning("[register_all] Hub attach failed via %s: %s", modname, e)
                return
    LOG.info("[register_all] Hub skipped: No module named 'hub'")


def register_all(app: Any) -> Any:
    """Main orchestration entry point for Flask app."""
    # Keep logging lightweight: Ester has its own logging setup elsewhere.
    _attach_cors_if_enabled(app)
    _attach_hub_if_available(app)

    # Route modules: keep the list short and stable.
    # Missing modules are acceptable; they will be logged and skipped.
    route_modules: Sequence[str] = [
        # core
        "routes.health_routes",
        "routes.docs_routes",
        "routes.memory_routes",
        "routes.telegram_routes",
        "routes.messaging_register_all",

        # optional (stubs provided in patch)
        "routes.admin_routes",
        "routes.telemetry_routes",
        "routes.tools_routes",
        "routes.file_routes",
        "routes.mission_routes",
        "routes.whatsapp_routes",
        "routes.chat_api_routes",

        # UI / MVP
        "routes.docs_ui_routes",
        "routes.mvp_manifest_routes",
        "routes.mvp_autonomy_routes",
        "routes.admin_portable_firststart",
        "routes.admin_portable_links",
        "routes.admin_portable_metrics",
        "routes.admin_portable_files",
    ]

    # Allow extra modules by env: comma-separated fully-qualified names.
    extra = os.getenv("ESTER_EXTRA_ROUTE_MODULES", "").strip()
    if extra:
        for part in extra.split(","):
            part = part.strip()
            if part:
                route_modules = list(route_modules) + [part]  # type: ignore[assignment]

    fn_candidates = ("register", "register_blueprints", "register_routes", "register_api", "init_app", "setup")

    for modname in route_modules:
        m = _optional_import(modname)
        if not m:
            continue
        _call_first_available(m, app, fn_candidates)

    # Last resort: auto-register blueprints that were imported but not wired.
    if _env_truthy("ESTER_AUTOSCAN_BLUEPRINTS", "1"):
        _scan_and_register_blueprints(app, "routes")

    return app


def register(app: Any) -> Any:
    """Alias to register_all for backward compatibility."""
    return register_all(app)


def register_all_skills(skill_manager: Any) -> Any:
    """Skill registration entry point expected by run_ester_fixed.py.

    We keep this as a thin shim to avoid import cycles and heavy imports at module load time.
    """
    try:
        from modules.register_all import register_all_skills as _impl  # type: ignore
        return _impl(skill_manager)
    except Exception as e:
        LOG.warning("[register_all] Skills skipped: %s", e)
        return None