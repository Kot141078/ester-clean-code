# -*- coding: utf-8 -*-
"""modules.register_all

Registration skills v SkillManager.

Requirements sovmestimosti:
- canonical import: `from modules.register_all import register_all_skills`.
- root register_all.py ostavlen kak back-compat shim dlya starykh vyzovov.
- Zdes lezhit realnaya realizatsiya.

Behavior:
- *Nikogda* ne padaem iz-za otsutstviya neobyazatelnykh skills.
- Registriruem only to, what really imports."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any, Callable, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

LOG = logging.getLogger("modules.register_all")
_WARNED_BAD_SKILL_MANAGER = False
_ROOT_APP_REGISTER: Optional[Callable[[Any], Any]] = None
_ROOT_APP_REGISTER_RESOLVED = False


def _try_import(module: str, name: str) -> Optional[Callable]:
    try:
        import importlib
        m = importlib.import_module(module)
        return getattr(m, name, None)
    except Exception as e:
        LOG.info("[register_all_skills] optional import failed: %s.%s: %s", module, name, e)
        return None


def _add_skill(skill_manager: Any, *, name: str, func: Callable, tags: list[str], description: str) -> None:
    try:
        if hasattr(skill_manager, "add_skill") and callable(getattr(skill_manager, "add_skill")):
            skill_manager.add_skill(name=name, func=func, tags=tags, description=description)  # type: ignore
            LOG.info("[register_all_skills] Registered: %s", name)
            return
        if hasattr(skill_manager, "add") and callable(getattr(skill_manager, "add")):
            skill_manager.add({"name": name, "func": func, "tags": tags, "description": description})  # type: ignore
            LOG.info("[register_all_skills] Registered: %s", name)
            return
        if hasattr(skill_manager, "register_skill") and callable(getattr(skill_manager, "register_skill")):
            # Minimal adapter for older SkillManager implementations
            class _FuncSkill:
                @property
                def name(self) -> str:
                    return name

                @property
                def description(self) -> str:
                    return description or "Skill"

                @property
                def parameters(self) -> dict:
                    return {"tags": ",".join(tags or [])}

                def execute(self, **kwargs):  # type: ignore
                    return func(**kwargs)

            skill_manager.register_skill(_FuncSkill())  # type: ignore
            LOG.info("[register_all_skills] Registered: %s", name)
            return
    except Exception as e:
        LOG.warning("[register_all_skills] Failed to register %s: %s", name, e)


def _can_register_skills(skill_manager: Any) -> bool:
    return bool(
        skill_manager
        and (
            (hasattr(skill_manager, "add_skill") and callable(getattr(skill_manager, "add_skill")))
            or (hasattr(skill_manager, "add") and callable(getattr(skill_manager, "add")))
            or (hasattr(skill_manager, "register_skill") and callable(getattr(skill_manager, "register_skill")))
        )
    )

def _looks_like_flask_app(obj: Any) -> bool:
    if obj is None:
        return False
    # Heuristics only; avoid importing Flask here.
    if hasattr(obj, "register_blueprint") or hasattr(obj, "blueprints"):
        return True
    name = obj.__class__.__name__
    return name in {"Flask", "Quart", "Sanic"}


def _resolve_root_app_register() -> Optional[Callable[[Any], Any]]:
    """Resolve root `register_all.py` without relying on ambiguous bare imports."""
    global _ROOT_APP_REGISTER, _ROOT_APP_REGISTER_RESOLVED
    if _ROOT_APP_REGISTER_RESOLVED:
        return _ROOT_APP_REGISTER
    _ROOT_APP_REGISTER_RESOLVED = True

    try:
        root_path = Path(__file__).resolve().parents[1] / "register_all.py"
        if not root_path.is_file():
            return None
        spec = importlib.util.spec_from_file_location("_ester_root_register_all", str(root_path))
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        fn = getattr(module, "register_all", None)
        if callable(fn):
            _ROOT_APP_REGISTER = fn
            return _ROOT_APP_REGISTER
    except Exception as e:
        LOG.info("[register_all] root resolver failed: %s", e)
    return None


def _register_flask_app(app: Any) -> bool:
    root_fn = _resolve_root_app_register()
    if callable(root_fn):
        try:
            root_fn(app)
            return True
        except Exception as e:
            LOG.warning("[register_all] root app registration failed: %s", e)

    try:
        from routes.register_all import register as _routes_register  # type: ignore

        _routes_register(app)
        return True
    except Exception as e:
        LOG.warning("[register_all] routes app registration failed: %s", e)
    return False


def register_all_skills(skill_manager: Any) -> None:
    global _WARNED_BAD_SKILL_MANAGER
    if not _can_register_skills(skill_manager):
        if not _WARNED_BAD_SKILL_MANAGER:
            LOG.warning("[register_all_skills] SkillManager has no add_skill/add/register_skill method")
            _WARNED_BAD_SKILL_MANAGER = True
        return

    # The skill modules are canonical (as in your old file).
    # If something is missing, that's normal.
    skills = [
        ("skills.ingest", "ingest_skill", "ingest", ["system", "file"], "Zagruzka i indeksirovanie faylov/teksta"),
        ("skills.analyze", "analyze_skill", "analyze", ["analysis"], "Analiz teksta/struktury/logov"),
        ("skills.file_search", "file_search_skill", "file_search", ["system", "file"], "Poisk po faylam/papkam"),
        ("skills.memory_manage", "memory_manage_skill", "memory_manage", ["memory"], "Memory management (entries/tags/clearing)"),
        ("skills.web_search", "web_search_skill", "web_search", ["system", "web"], "Internet search (if allowed)"),
        ("skills.provider_info", "provider_info_skill", "provider_info", ["system"], "Provider/Model Information"),
        ("skills.tools", "tools_skill", "tools", ["system"], "Sistemnye instrumenty/diagnostika"),
    ]

    # Plus: sometimes skills can live in modules.skills_*
    fallback_skills = [
        ("modules.skills_ingest", "ingest_skill", "ingest", ["system", "file"], "Zagruzka i indeksirovanie faylov/teksta"),
        ("modules.skills_analyze", "analyze_skill", "analyze", ["analysis"], "Analiz teksta/struktury/logov"),
        ("modules.skills_file_search", "file_search_skill", "file_search", ["system", "file"], "Poisk po faylam/papkam"),
        ("modules.skills_memory_manage", "memory_manage_skill", "memory_manage", ["memory"], "Memory management (entries/tags/clearing)"),
        ("modules.skills_web_search", "web_search_skill", "web_search", ["system", "web"], "Internet search (if allowed)"),
        ("modules.skills_provider_info", "provider_info_skill", "provider_info", ["system"], "Provider/Model Information"),
        ("modules.skills_tools", "tools_skill", "tools", ["system"], "Sistemnye instrumenty/diagnostika"),
    ]

    any_registered = False

    for mod, attr, name, tags, desc in skills:
        fn = _try_import(mod, attr)
        if callable(fn):
            _add_skill(skill_manager, name=name, func=fn, tags=tags, description=desc)
            any_registered = True

    if not any_registered:
        # if skills.* is not found, try modules.skills_*
        for mod, attr, name, tags, desc in fallback_skills:
            fn = _try_import(mod, attr)
            if callable(fn):
                _add_skill(skill_manager, name=name, func=fn, tags=tags, description=desc)
                any_registered = True


def register_all(skill_manager: Any) -> None:
    """Compatibility alias for callers expecting register_all()."""
    # If a Flask app is passed here by mistake, delegate to root register_all.
    if _looks_like_flask_app(skill_manager) and not _can_register_skills(skill_manager):
        if not _register_flask_app(skill_manager):
            LOG.warning("[register_all] app registration failed: no compatible registrar")
        return
    register_all_skills(skill_manager)
