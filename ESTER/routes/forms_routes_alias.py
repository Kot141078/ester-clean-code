# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict
import importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["register"]

def _import_first(*names: str):
    for n in names:
        try:
            return importlib.import_module(n)
        except Exception:
            pass
    return None

def register(app) -> Dict[str, Any]:
    mod = _import_first(
        "ESTER.routes.forms_routes",
        "ester.routes.forms_routes",
        "routes.forms_routes",
        "forms_routes",
    )
    if mod and hasattr(mod, "register"):
        return mod.register(app)  # type: ignore[attr-defined]
    return {"ok": False, "error": "forms_routes.register not found"}