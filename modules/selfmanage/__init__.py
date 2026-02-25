# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules/selfmanage - sovmestimost s istoricheskimi importami.
Mosty:
- Yavnyy: (selfmanage ↔ self) — reeksportiruem node_inventory i dr. iz modules.self.*.
- Skrytyy #1: (DX ↔ Nadezhnost) — ne menyaem starye importy v kodovoy baze.
- Skrytyy #2: (Memory ↔ Otkat) — A/B flag mozhno ispolzovat iz vneshnego okruzheniya.

Zemnoy abzats:
Nekotorye fayly import modules.selfmanage.*, a kod zhivet v modules/self/*. This package mostit razryv.
# c=a+b"""
from importlib import import_module
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    node_inventory = import_module("modules.self.node_inventory")  # type: ignore
except Exception:
    node_inventory = None  # type: ignore

__all__ = ["node_inventory"]