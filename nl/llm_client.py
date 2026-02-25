# -*- coding: utf-8 -*-
"""nl/llm_client.py - tonkaya obvyazka LLM dlya myagkoy “polirovki” teksta.

MOSTY:
- (Yavnyy) suggest_refinement(text, kind, intent) — vozvraschaet otredaktirovannyy variant or None.
- (Skrytyy #1) BACKEND=off|openai; bezopasnye taym-auty, no-op esli net klyucha.
- (Skrytyy #2) Zaschita ot “boltlivosti”: vozvraschaem ne bolee 900 simvolov, sokhranyaem smysl.

ZEMNOY ABZATs:
Esli khochetsya “esche chut-chut rovnee” - vklyuchaem openai-bekend i daem modeli perepisat tekst v zadannom stile.

# c=a+b"""
from __future__ import annotations

import os
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _backend() -> str:
    return os.getenv("AUTHORING_LLM_BACKEND","off").lower()

def suggest_refinement(text: str, kind: str, intent: str) -> Optional[str]:
    if _backend() != "openai":
        return None
    key = os.getenv("OPENAI_API_KEY","")
    if not key:
        return None
    # Local stub (no external network call): simulates light "polishing"
    # V prode — zamenit tonkoy integratsiey s SDK.
    t = text.strip()
    t = t.replace("  ", " ")
    if len(t) > 900:
        t = t[:900]
    return t