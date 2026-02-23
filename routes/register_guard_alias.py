# -*- coding: utf-8 -*-
"""
routes/register_guard_alias.py — bezopasnaya registratsiya routov i gibkie aliasy importa.

Mosty:
- Yavnyy: (Flask ↔ Routy) — obertka AddRuleGuard perekhvatyvaet add_url_rule i ustranyaet «overwriting endpoint» i otsutstvie view_func.
- Skrytyy #1: (Arkhitektura ↔ Sovmestimost) — import_route_module probuet ester.routes.* i routes.* bez padeniy.
- Skrytyy #2: (A/B ↔ Bezopasnost) — with_guard_if_B vklyuchaet zaschitu tolko v rezhime B cherez peremennuyu ESTER_ROUTES_AB.

Zemnoy abzats:
Dumay o module kak o «predokhranitele» v raspredelitelnom schite: esli liniyu uzhe zanyali — my ne vybivaem avtomat,
a podklyuchaemsya k sosednemu svobodnomu slotu; esli pribora esche net — ne tyanem provod v pustotu.

# c=a+b
"""
from __future__ import annotations

from types import ModuleType
from typing import Optional, Callable
import importlib
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class AddRuleGuard:
    """Kontekstnyy menedzher, vremenno zamenyayuschiy app.add_url_rule na bezopasnyy variant."""
    def __init__(self, app):
        self.app = app
        self._orig = app.add_url_rule

    def __enter__(self):
        def safe_add(rule, endpoint=None, view_func=None, **options):
            # Esli endpoint izvesten, a view_func ne peredan — poprobuem nayti uzhe zaregistrirovannuyu funktsiyu
            if view_func is None and endpoint and endpoint in self.app.view_functions:
                view_func = self.app.view_functions[endpoint]
            try:
                return self._orig(rule, endpoint=endpoint, view_func=view_func, **options)
            except AssertionError as e:
                msg = str(e)
                if "overwriting an existing endpoint function" in msg:
                    # Konflikt imen: akkuratno podberem novoe imya endpoint_X
                    base = endpoint or (getattr(view_func, "__name__", "endpoint") if view_func else "endpoint")
                    i = 2
                    new_ep = f"{base}_{i}"
                    while new_ep in self.app.view_functions:
                        i += 1
                        new_ep = f"{base}_{i}"
                    return self._orig(rule, endpoint=new_ep, view_func=view_func, **options)
                if "expected view func if endpoint is not provided" in msg:
                    # Net fakticheskoy funktsii — propuskaem svyazyvanie, no ne padaem
                    logger = getattr(self.app, "logger", None)
                    if logger:
                        logger.warning("RoutesGuard: skip rule=%r endpoint=%r (no view_func yet)", rule, endpoint)
                    return None
                # Prochie AssertionError — probrasyvaem
                raise
        self.app.add_url_rule = safe_add
        return self

    def __exit__(self, exc_type, exc, tb):
        self.app.add_url_rule = self._orig
        return False

def _try_import(name: str) -> Optional[ModuleType]:
    try:
        return importlib.import_module(name)
    except Exception:
        return None

def import_route_module(*candidates: str) -> Optional[ModuleType]:
    """Vozvraschaet pervyy uspeshno importirovannyy modul iz spiska kandidatov."""
    for c in candidates:
        m = _try_import(c)
        if m is not None:
            return m
    return None

def with_guard_if_B(app, fn: Callable[[], None]) -> None:
    """Vklyuchaet AddRuleGuard(app) tolko v rezhime B (ESTER_ROUTES_AB=B), inache prosto vyzyvaet fn()."""
    mode = (os.getenv("ESTER_ROUTES_AB") or "A").upper()[:1]
    if mode == "B":
        with AddRuleGuard(app):
            fn()
    else:
        fn()

def register(app) -> None:
    """Neytralnyy entrypoint dlya sovmestimosti s avtoskriptami registratsii.
    Nichego ne delaet i nichego ne registriruet."""
    return None