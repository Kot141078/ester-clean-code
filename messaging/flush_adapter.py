# -*- coding: utf-8 -*-
"""messaging/flush_adapter.py - pereklyuchatel broadcast↔styled_broadcast po ENV.

MOSTY:
- (Yavnyy) choose_broadcast(keys,intent,kind) — edinaya tochka, kotoruyu mozhno ispolzovat v lyubykh flushakh/rassylkakh.
- (Skrytyy #1) Pri NUDGES_USE_STYLED=1 vyzyvaet messaging.styled_broadcast.send_styled_broadcast.
- (Skrytyy #2) Signatury iskhodnogo send_broadcast ne menyaem.

ZEMNOY ABZATs:
Khotite, chtoby Ester zvuchala "po-chelovecheski" - vklyuchite flag i ispolzuyte etot adapter vmesto pryamogo vyzova.

# c=a+b"""
from __future__ import annotations

import os
from typing import List, Optional, Dict, Any

from messaging.broadcast import send_broadcast as _plain
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    from messaging.styled_broadcast import send_styled_broadcast as _styled
except Exception:
    _styled = None  # type: ignore

def choose_broadcast(keys: List[str], intent: str, adapt_kind: Optional[str] = None) -> Dict[str, Any]:
    if os.getenv("NUDGES_USE_STYLED","0") == "1" and _styled is not None:
        return _styled(keys, intent, adapt_kind=adapt_kind)
    return _plain(keys, intent, adapt_kind=adapt_kind)