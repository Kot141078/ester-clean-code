# -*- coding: utf-8 -*-
"""modules/mm_compat.py - sovmestimost "patcha pamyati".

MOSTY:
- (Yavnyy) patch() — no-op, vozvraschaet False (nichego ne primenyalos).
- (Skrytyy #1) Predostavlyaet patch_memory_manager(), vyravnivayuschiy API .cards.
- (Skrytyy #2) Glushit WARNING “mm_compat ne nayden”, sokhranyaya tsepochku zagruzki.

ZEMNOY ABZATs:
Zaglushaem noise na shine - poezd idet, dazhe esli modul tonkoy nastroyki pamyati otsutstvuet.

# c=a+b"""
from __future__ import annotations

import os
from typing import Any


def patch() -> bool:
    return False


class _CardsCompat:
    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def add_card(self, header: str, body: str, tags: Any = None, weight: float = 0.5, **kwargs: Any) -> str:
        user = str(kwargs.get("user") or os.getenv("MM_COMPAT_USER") or "default")
        parts = [str(part).strip() for part in (header, body) if str(part).strip()]
        text = "\n".join(parts) if parts else str(body or header or "")
        return self._manager.medium_cards.add_card(user=user, text=text, tags=list(tags or []), weight=weight)


def patch_memory_manager() -> bool:
    try:
        from memory_manager import MemoryManager  # type: ignore
    except Exception:
        return False

    if getattr(MemoryManager, "_mm_compat_cards_patched", False):
        return True

    def _get_cards(self: Any) -> _CardsCompat:
        return _CardsCompat(self)

    setattr(MemoryManager, "cards", property(_get_cards))
    setattr(MemoryManager, "_mm_compat_cards_patched", True)
    return True
# c=a+b
