
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.compat.route_guard — optsionalnaya zaschita routov (FastAPI/Flask).
Vklyuchaetsya ENV: ESTER_ROUTE_GUARD=1. Bezopasnyy A/B-slot.

Mosty:
- Yavnyy: predotvraschaem povtornuyu registratsiyu odinakovykh (method,path).
- Skrytyy #1: (DX ↔ Nablyudaemost) — pechataem preduprezhdenie pri duble.
- Skrytyy #2: (Bezopasnost ↔ Stabilnost) — ne brosaem isklyucheniya, prosto ignoriruem dubl.

Zemnoy abzats:
V bolshom proekte odna i ta zhe ruchka mozhet registrirovatsya iz raznykh mest.
Etot patch ne daet ey slomat server kolliziyami — berezhno propuskaem tolko pervoe obyavlenie.
# c=a+b
"""
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
if os.getenv("ESTER_ROUTE_GUARD","0") not in {"0","","false","False"}:
    # FastAPI
    try:
        import fastapi
        from fastapi.applications import FastAPI  # type: ignore
        _orig_add = FastAPI.add_api_route
        _seen = set()
        def _guard(self, path, endpoint, *, methods=None, **kw):
            methods = methods or {"GET"}
            key = tuple(sorted((m.upper() for m in methods))) + (path,)
            if key in _seen:
                try:
                    print(f"[RouteGuard] skip duplicate FastAPI route {key}")
                except Exception:
                    pass
                return  # swallow duplicate
            _seen.add(key)
            return _orig_add(self, path, endpoint, methods=methods, **kw)
        FastAPI.add_api_route = _guard  # type: ignore
    except Exception:
        pass

    # Flask
    try:
        from flask import Flask  # type: ignore
        _orig_rule = Flask.add_url_rule
        _seen_f = set()
        def _guard_rule(self, rule, endpoint=None, view_func=None, provide_automatic_options=None, **options):
            methods = options.get("methods") or {"GET"}
            key = tuple(sorted((m.upper() for m in methods))) + (rule,)
            if key in _seen_f:
                try:
                    print(f"[RouteGuard] skip duplicate Flask route {key}")
                except Exception:
                    pass
                return  # swallow duplicate
            _seen_f.add(key)
            return _orig_rule(self, rule, endpoint=endpoint, view_func=view_func, provide_automatic_options=provide_automatic_options, **options)
        Flask.add_url_rule = _guard_rule  # type: ignore
    except Exception:
        pass