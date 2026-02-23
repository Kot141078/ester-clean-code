# -*- coding: utf-8 -*-
"""
security/keys.py — upravlenie P2P-klyuchami HMAC (rotatsiya, kid).

MOSTY:
- (Yavnyy) Podderzhka P2P_HMAC_KEYS="kid1:key1,kid2:key2" i naslediya P2P_HMAC_KEY (kid=default).
- (Skrytyy #1) Bezopasnyy parsing: pustye/bitye pary ignoriruyutsya; klyuchi trimmiruyutsya.
- (Skrytyy #2) Vozvrat spiska aktivnykh kid dlya otladki/metrik (bez utechki samikh klyuchey).

ZEMNOY ABZATs:
Pozvolyaet krutit klyuchi bez ostanovki servisa: novyy pomechaem kak `main`, staryy — kak `prev` i derzhim do istecheniya TTL.

# c=a+b
"""
from __future__ import annotations
import os
from typing import Dict, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _parse_pairs(s: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw in s.split(","):
        raw = raw.strip()
        if not raw or ":" not in raw:
            continue
        kid, key = raw.split(":", 1)
        kid = kid.strip()
        key = key.strip()
        if not kid or not key:
            continue
        out[kid] = key
    return out

def load_keys() -> Dict[str, str]:
    env = (os.getenv("P2P_HMAC_KEYS") or "").strip()
    if env:
        return _parse_pairs(env)
    legacy = (os.getenv("P2P_HMAC_KEY") or "").strip()
    if legacy:
        return {"default": legacy}
    return {}

def get_key(kid: Optional[str]) -> Optional[str]:
    keys = load_keys()
    if not keys:
        return None
    if kid and kid in keys:
        return keys[kid]
    # Net kid — po umolchaniyu probuem vse (dlya sovmestimosti)
    return None

def list_kids() -> Tuple[str, ...]:
    return tuple(load_keys().keys())

def primary_kid() -> Optional[str]:
    keys = load_keys()
    if not keys:
        return None
    # evristika: esli est 'main' — vernut ego; inache pervyy po poryadku env
    if "main" in keys:
        return "main"
    return next(iter(keys.keys()))