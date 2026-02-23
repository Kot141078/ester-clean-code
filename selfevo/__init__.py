# -*- coding: utf-8 -*-
"""
selfevo — proksi-paket k realnomu kodu v modules.selfevo.
Nuzhen dlya sovmestimosti s importami `import selfevo.*`.
"""
from __future__ import annotations
import importlib, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_TARGET_PKG = 'modules.selfevo'
_pkg = importlib.import_module(_TARGET_PKG)

__path__ = list(getattr(_pkg, '__path__', []))  # type: ignore
__package__ = 'selfevo'

def __getattr__(name: str):
    if name == "load_tests":
        raise AttributeError("selfevo has no load_tests hook")
    mod = importlib.import_module(f"{_TARGET_PKG}.{name}")
    sys.modules[f"selfevo.{name}"] = mod
    globals()[name] = mod
    return mod
