# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in text)[:64] or "ep"

def _wrap_class(cls):
    if not hasattr(cls, "add_url_rule"):
        return False
    orig = cls.add_url_rule  # func/descriptor na klasse
    if getattr(orig, "__ester_ep_shim__", False):
        return False

    def safe_add_url_rule(self, rule: str, endpoint: str | None = None,
                          view_func: Any | None = None, **options: Any) -> Any:
        # 1) does not crash if there is no view_function
        if view_func is None:
            return None
        # 2) unikaliziruem endpoint pri LYuBOY kollizii
        ep = (str(endpoint) if endpoint is not None else
              str(getattr(view_func, "__name__", "view"))).strip() or "view"
        vmap = getattr(self, "view_functions", {})
        if isinstance(vmap, dict) and ep in vmap:
            suf = _slug(rule)
            base = f"{ep}__{suf}"
            cand = base
            i = 1
            while cand in vmap:
                i += 1
                cand = f"{base}_{i}"
            endpoint = cand
        return orig(self, rule, endpoint=endpoint, view_func=view_func, **options)

    setattr(safe_add_url_rule, "__ester_ep_shim__", True)
    cls.add_url_rule = safe_add_url_rule  # podmenyaem metod klassa
    return True

def _patch_classes() -> bool:
    patched = False
    try:
        import flask  # type: ignore
        patched |= _wrap_class(flask.Flask)
        try:
            from flask.scaffold import Scaffold  # type: ignore
            patched |= _wrap_class(Scaffold)
        except Exception:
            pass
        try:
            from flask.blueprints import Blueprint  # type: ignore
            patched |= _wrap_class(Blueprint)
        except Exception:
            pass
        return patched
    except Exception:
        return False

def register(app) -> dict:
    if os.environ.get("ESTER_ROUTE_EP_SHIM_AB", "A") != "A":
        return {"ok": True, "patched": False, "why": "AB=B"}
    try:
        ok = _patch_classes()
        return {"ok": bool(ok), "patched": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
# c=a+b