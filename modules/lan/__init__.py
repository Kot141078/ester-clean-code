
# -*- coding: utf-8 -*-
"""modules.lan - dinamicheskiy most k LAN-* slushatelyam.
Mosty:
- Yavnyy: (modules.lan.X ↔ listeners.lan_X)
- Skrytyy #1: (P2P ↔ Transport) — pozvolyaet mappit na p2p_*.
- Skrytyy #2: (Diagnostika ↔ UI) — padeniya importov prevraschaet v AttributeError s podskazkoy.

Zemnoy abzats:
Setevye nablyudateli neredko zhivut v `listeners/*`. My ne dubliruem kod, a perenapravlyaem importy.
# c=a+b"""
from __future__ import annotations
import importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def __getattr__(name: str):
    for target in (f"listeners.lan_{name}", f"lan.{name}", f"listeners.{name}"):
        try:
            return importlib.import_module(target)
        except Exception:
            pass
    raise AttributeError(f"modules.lan: unknown '{name}'")