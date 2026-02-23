# -*- coding: utf-8 -*-
"""
app_plugins.compat_loop_status — dobavlyaet v modules.thinking.loop_full simvol status,
esli on otsutstvuet, mapya ego na modules.act.runner.status.
MOSTY: (yavnyy) thinking.loop_full ↔ act.runner; (skrytye) Flask-routy ↔ unifikatsiya API.
ZEMNOY ABZATs: ne trogaem iskhodnik loop_full.py — tolko dobavlyaem atribut pri importe.
# c=a+b
"""
from __future__ import annotations
import os
import importlib
from types import ModuleType
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_ENV = "ESTER_LOOP_STATUS_AB"  # A=vkl (defolt), B=vykl

def _mk_status_alias():
    try:
        runner = importlib.import_module("modules.act.runner")
    except Exception as e:
        def _fallback() -> Dict[str, Any]:
            return {"ok": False, "err": f"runner_import:{e}"}
        return _fallback

    def _status() -> Dict[str, Any]:
        try:
            return runner.status()  # type: ignore[attr-defined]
        except Exception as ex:
            return {"ok": False, "err": f"runner_status:{ex}"}
    return _status

def apply() -> bool:
    if os.environ.get(AB_ENV, "A") != "A":
        return False  # vyklyucheno cherez AB
    try:
        lf: ModuleType = importlib.import_module("modules.thinking.loop_full")
        if not hasattr(lf, "status"):
            setattr(lf, "status", _mk_status_alias())
        return True
    except Exception:
        return False