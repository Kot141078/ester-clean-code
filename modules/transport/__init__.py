
# -*- coding: utf-8 -*-
"""modules.transport - tonkiy transportnyy layer (p2p/lan/fs).
Mosty:
- Yavnyy: send()/recv() — bezopasnye default.
- Skrytyy #1: (listeners ↔ transport) — try p2p_spooler as drayver, if available.
- Skrytyy #2: (Inzheneriya ↔ Nadezhnost) — ne brosaem isklyucheniya pri otsutstvii transporta.

Zemnoy abzats:
Dazhe esli polnotsennyy transport ne gotov, API ne dolzhen valit prilozhenie.
# c=a+b"""
from __future__ import annotations
import importlib
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _p2p():
    try:
        return importlib.import_module("listeners.p2p_spooler")
    except Exception:
        return None

def send(topic: str, payload: bytes) -> bool:
    p = _p2p()
    if p and hasattr(p, "send"):
        try:
            return bool(p.send(topic, payload))
        except Exception:
            return False
    return False

def recv(topic: str) -> Optional[bytes]:
    p = _p2p()
    if p and hasattr(p, "recv"):
        try:
            return p.recv(topic)
        except Exception:
            return None
    return None