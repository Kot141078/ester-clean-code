# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.tools.route_guard — myagkiy storozh dublikatov routov dlya FastAPI/Flask.

Ispolzovanie (ruchnaya aktivatsiya — drop-in):
    from modules.tools import route_guard as rg
    rg.enable_for_fastapi(app)  # ili rg.enable_for_flask(app)

ENV:
- ESTER_ROUTE_GUARD=1 — obschiy flag vklyucheniya (po umolchaniyu vyklyucheno).
- ESTER_ROUTE_GUARD_AB=A|B — A: vklyucheno; B: no-op.
- ESTER_ROUTE_GUARD_VERBOSE=1 — pechatat "RouteGuard ..." pri propuskakh.

Mosty:
- Yavnyy: patchim add_api_route (FastAPI) / add_url_rule (Flask).
- Skrytyy #1: A/B-slot dlya bystrogo otkata.
- Skrytyy #2: sovmestim s otchetom routes_http (odna i ta zhe model kolliziy).

Zemnoy abzats:
Kak obratnyy klapan: esli takoy zhe (method,path) uzhe est, ne puskaem dublikat dalshe po trube.
# c=a+b
"""
import os
from typing import Set, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ENABLED = os.getenv("ESTER_ROUTE_GUARD","0") in {"1","true","True"}
AB = os.getenv("ESTER_ROUTE_GUARD_AB","A").upper().strip() or "A"
VERBOSE = os.getenv("ESTER_ROUTE_GUARD_VERBOSE","1") not in {"0","false","False"}

def _log(msg: str) -> None:
    if VERBOSE:
        print(f"[RouteGuard] {msg}")

def enable_for_fastapi(app) -> bool:
    if not ENABLED or AB == "B":
        return False
    try:
        router = getattr(app, "router", None)
        if router is None or not hasattr(router, "add_api_route"):
            return False
        seen: Set[Tuple[str,str]] = set()
        # Initsializatsiya uzhe imeyuschimisya
        try:
            for r in getattr(app, "routes", []):
                methods = getattr(r, "methods", None) or []
                path = getattr(r, "path", None) or getattr(r, "path_format", None)
                for m in methods:
                    seen.add((str(m).upper(), str(path)))
        except Exception:
            pass
        orig = router.add_api_route
        def wrapped(path, endpoint, **kw):
            methods = kw.get("methods") or ["GET"]
            # FastAPI mozhet takzhe probrasyvat metody cherez "methods" ili deduce iz endpoint
            # Normalizuem
            ms = [str(m).upper() for m in (list(methods) if isinstance(methods, (list,set,tuple)) else [methods])]
            skip = False
            for m in ms:
                if (m, str(path)) in seen:
                    _log(f"skip duplicate FastAPI route ('{m}', '{path}')")
                    skip = True
            if skip:
                return None
            for m in ms:
                seen.add((m, str(path)))
            return orig(path, endpoint, **kw)
        router.add_api_route = wrapped  # type: ignore
        _log("enabled for FastAPI")
        return True
    except Exception:
        return False

def enable_for_flask(app) -> bool:
    if not ENABLED or AB == "B":
        return False
    try:
        if not hasattr(app, "add_url_rule"):
            return False
        seen: Set[Tuple[str,str]] = set()
        # Initsializatsiya uzhe imeyuschimisya
        try:
            url_map = getattr(app, "url_map", None)
            if url_map is not None:
                for r in url_map.iter_rules():
                    methods = getattr(r, "methods", None) or []
                    for m in methods:
                        seen.add((str(m).upper(), str(r.rule)))
        except Exception:
            pass
        orig = app.add_url_rule
        def wrapped(rule, endpoint=None, view_func=None, **options):
            methods = options.get("methods") or {"GET"}
            ms = [str(m).upper() for m in (list(methods) if isinstance(methods, (list,set,tuple)) else [methods])]
            skip = False
            for m in ms:
                if (m, str(rule)) in seen:
                    _log(f"skip duplicate Flask route ('{m}', '{rule}')")
                    skip = True
            if skip:
                return None
            for m in ms:
                seen.add((m, str(rule)))
            return orig(rule, endpoint=endpoint, view_func=view_func, **options)
        app.add_url_rule = wrapped  # type: ignore
        _log("enabled for Flask")
        return True
    except Exception:
        return False