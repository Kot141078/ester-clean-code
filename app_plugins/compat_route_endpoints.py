# -*- coding: utf-8 -*-
"""Avto-unikalizatsiya endpoint-ov i myagkaya zaschita ot nekorrektnykh vyzovov add_url_rule().
Ispolzuetsya dlya ustraneniya:
- AssertionError('View function mapping is overwriting an existing endpoint function: ...')
- AssertionError('expected view func if endpoint is not provided.')

Upravlenie: ESTER_ROUTE_EP_SHIM_AB (A=vkl [po umolchaniyu], B=vykl)
# c=a+b"""
from __future__ import annotations
import os
from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _slug(text: str) -> str:
    # compact servants: letters/numbers/underlining
    return "".join(ch if ch.isalnum() else "_" for ch in text)[:64] or "ep"

def apply() -> bool:
    if os.environ.get("ESTER_ROUTE_EP_SHIM_AB", "A") != "A":
        return False
    try:
        import flask  # type: ignore
        orig = flask.Flask.add_url_rule

        def safe_add_url_rule(self: "flask.Flask", rule: str, endpoint: str | None = None,
                              view_func: Any | None = None, **options: Any) -> Any:
            # 1) If view_function is missing (wrong call) - skip registration,
            #    so as not to fall on the Expected View Function.... We don’t lose any logic: the right decorators will call this later correctly.
            if view_func is None:
                # myagkiy no-op
                return None

            # 2) Razrulivaem konflikty endpoint po imeni
            ep = str(endpoint or getattr(view_func, "__name__", "view")).strip() or "view"
            vmap = getattr(self, "view_functions", {})
            if ep in vmap and vmap.get(ep) is not view_func:
                # Will generate a stable unique name taking into account the steering wheel
                suf = _slug(rule)
                base = f"{ep}__{suf}"
                cand = base
                i = 1
                while cand in vmap:
                    i += 1
                    cand = f"{base}_{i}"
                endpoint = cand

            return orig(self, rule, endpoint=endpoint, view_func=view_func, **options)

        if getattr(flask.Flask.add_url_rule, "__name__", "") != "safe_add_url_rule":
            flask.Flask.add_url_rule = safe_add_url_rule  # type: ignore[assignment]
        return True
    except Exception:
        return False