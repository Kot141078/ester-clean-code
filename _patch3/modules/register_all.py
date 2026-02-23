# -*- coding: utf-8 -*-
"""modules.register_all

Registratsiya skills v SkillManager.

Trebovanie sovmestimosti:
- run_ester_fixed.py delaet: `from register_all import register_all_skills`
  poetomu root register_all.py dolzhen reeksportirovat etot simvol.
- Zdes lezhit realnaya realizatsiya.

Povedenie:
- *Nikogda* ne padaem iz-za otsutstviya neobyazatelnykh skills.
- Registriruem tolko to, chto realno importiruetsya.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

LOG = logging.getLogger("modules.register_all")


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
        elif hasattr(skill_manager, "add") and callable(getattr(skill_manager, "add")):
            # Fallback: pass dict-like skill
            skill_manager.add({"name": name, "func": func, "tags": tags, "description": description})  # type: ignore
        else:
            LOG.warning("[register_all_skills] SkillManager has no add_skill/add method")
            return
        LOG.info("[register_all_skills] Registered: %s", name)
    except Exception as e:
        LOG.warning("[register_all_skills] Failed to register %s: %s", name, e)


def register_all_skills(skill_manager: Any) -> None:
    if not skill_manager:
        return

    # Canonical skill modules (kak v tvoem starom fayle).
    # Esli kakaya-to shtuka otsutstvuet — eto normalno.
    skills = [
        ("skills.ingest", "ingest_skill", "ingest", ["system", "file"], "Zagruzka i indeksirovanie faylov/teksta"),
        ("skills.analyze", "analyze_skill", "analyze", ["analysis"], "Analiz teksta/struktury/logov"),
        ("skills.file_search", "file_search_skill", "file_search", ["system", "file"], "Poisk po faylam/papkam"),
        ("skills.memory_manage", "memory_manage_skill", "memory_manage", ["memory"], "Upravlenie pamyatyu (zapisi/tegi/ochistka)"),
        ("skills.web_search", "web_search_skill", "web_search", ["system", "web"], "Poisk v internete (esli razresheno)"),
        ("skills.provider_info", "provider_info_skill", "provider_info", ["system"], "Informatsiya o provayderakh/modelyakh"),
        ("skills.tools", "tools_skill", "tools", ["system"], "Sistemnye instrumenty/diagnostika"),
    ]

    # Plyus: inogda skills mogut zhit v modules.skills_*
    fallback_skills = [
        ("modules.skills_ingest", "ingest_skill", "ingest", ["system", "file"], "Zagruzka i indeksirovanie faylov/teksta"),
        ("modules.skills_analyze", "analyze_skill", "analyze", ["analysis"], "Analiz teksta/struktury/logov"),
        ("modules.skills_file_search", "file_search_skill", "file_search", ["system", "file"], "Poisk po faylam/papkam"),
        ("modules.skills_memory_manage", "memory_manage_skill", "memory_manage", ["memory"], "Upravlenie pamyatyu (zapisi/tegi/ochistka)"),
        ("modules.skills_web_search", "web_search_skill", "web_search", ["system", "web"], "Poisk v internete (esli razresheno)"),
        ("modules.skills_provider_info", "provider_info_skill", "provider_info", ["system"], "Informatsiya o provayderakh/modelyakh"),
        ("modules.skills_tools", "tools_skill", "tools", ["system"], "Sistemnye instrumenty/diagnostika"),
    ]

    any_registered = False

    for mod, attr, name, tags, desc in skills:
        fn = _try_import(mod, attr)
        if callable(fn):
            _add_skill(skill_manager, name=name, func=fn, tags=tags, description=desc)
            any_registered = True

    if not any_registered:
        # esli skills.* ne naydeno — probuem modules.skills_*
        for mod, attr, name, tags, desc in fallback_skills:
            fn = _try_import(mod, attr)
            if callable(fn):
                _add_skill(skill_manager, name=name, func=fn, tags=tags, description=desc)