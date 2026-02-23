# -*- coding: utf-8 -*-
"""
thinking — sovmestimyy proksi-paket k realnomu kodu v modules.thinking.

Pochemu eto nuzhno:
  V proekte chast importov napisana kak `import thinking.*`,
  pri tom chto fakticheskiy kod lezhit v `modules/thinking/*`.
  Iz-za etogo vy vidite preduprezhdenie:
      "Myagkiy import: thinking.think_core nedostupen: No module named 'thinking'"

Etot paket delaet «thinking» vidimym i prozrachno proksiruet vse obrascheniya
v nastoyaschiy paket `modules.thinking`, bez kopirovaniya logiki i bez zaglushek.
"""
from __future__ import annotations
import importlib, pkgutil, types, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_TARGET_PKG_NAME = 'modules.thinking'
_target_pkg = importlib.import_module(_TARGET_PKG_NAME)

# Povtoryaem metadannye i put, chtoby pkgutil.walk_packages i t.p. rabotali.
__path__ = list(getattr(_target_pkg, '__path__', []))  # type: ignore
__package__ = 'thinking'
__all__ = []

def __getattr__(name: str):
    """
    Lenivaya podgruzka podmoduley kak atributov: `thinking.think_core`,
    `thinking.action_registry` i t.p.
    """
    if name == "load_tests":
        raise AttributeError("thinking has no load_tests hook")
    try:
        mod = importlib.import_module(f"{_TARGET_PKG_NAME}.{name}")
    except Exception as e:
        raise AttributeError(f"thinking: cannot import {name!r} from {_TARGET_PKG_NAME}: {e}") from e
    sys.modules[f"thinking.{name}"] = mod
    if name not in globals():
        globals()[name] = mod
    if name not in __all__:
        __all__.append(name)
    return mod

# Eksport bazovykh chasto ispolzuemykh simvolov (esli oni est v tselevom pakete)
for _sym in ('__version__',):
    if hasattr(_target_pkg, _sym):
        globals()[_sym] = getattr(_target_pkg, _sym)
