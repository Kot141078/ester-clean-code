
# -*- coding: utf-8 -*-
"""
modules/core/input_guard.py — tsentralizovannyy limiter teksta chata.

Mosty:
- (Yavnyy) chat_input_guard_adapter → normalizatsiya vkhoda dlya /chat/message.
- (Skrytyy #1) Telegram/desktop adaptery mogut pereispolzovat te zhe limity.
- (Skrytyy #2) LM Studio / drugie provaydery mogut chitat obschiy limit iz ENV.

Zemnoy abzats:
Kak mekhanicheskiy ogranichitel khoda rychaga: skolko by ni davili, shtok ne ukhodit dalshe
zhestkogo upora, zaschischaya sistemu ot peregruzki.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@dataclass
class GuardInfo:
    original_len: int
    effective_len: int
    limit: int
    trimmed: bool


def _env_int(name: str, default: int) -> int:
    try:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        return max(0, int(raw))
    except Exception:
        return default


DEFAULT_LIMIT = 16000


def get_effective_limit() -> int:
    """Vozvraschaet limit dlya vkhoda chata na osnove ENV."""
    limit = _env_int("ESTER_CHAT_MAX_INPUT_CHARS", DEFAULT_LIMIT)
    return limit or DEFAULT_LIMIT


def normalize_input(text: Optional[str]) -> Tuple[str, GuardInfo]:
    """Normalizuet vkhodnoy tekst i obrezaet po limitu.

    Kontrakt:
    - Ne kidaet isklyucheniy.
    - Vozvraschaet (stroka, GuardInfo).
    """
    if text is None:
        text = ""

    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            text = ""

    original_len = len(text)
    limit = get_effective_limit()

    if limit > 0 and original_len > limit:
        text = text[:limit]
        trimmed = True
    else:
        trimmed = False

    info = GuardInfo(
        original_len=original_len,
        effective_len=len(text),
        limit=limit,
        trimmed=trimmed,
    )
    return text, info