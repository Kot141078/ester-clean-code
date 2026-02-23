# -*- coding: utf-8 -*-
"""
nl/authoring_router.py — vybor stilya i finalnyy render teksta.

MOSTY:
- (Yavnyy) author_text(intent, recipient_kind|meta) + safe-LLM rasshirenie (off po umolchaniyu).
- (Skrytyy #1) Evristiki: email- ili tegi «lawyer/student/friend» → stil; inache — neutral.
- (Skrytyy #2) A/B-profil: AUTHORING_STYLE_AB=A|B; mgnovennyy otkat bez perezapuska.

ZEMNOY ABZATs:
Odin vyzov — i poluchaem chelovecheskiy tekst, kotoryy «lozhitsya» na adresata. Esli dostupna LLM — utochnyaem i poliruem.

# c=a+b
"""
from __future__ import annotations

import re
from typing import Dict, Optional

from nl.style_profiles import render_style
from nl.llm_client import suggest_refinement
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_RE_LAW = re.compile(r"(law|yurist|advokat|legal|attorney)", re.I)
_RE_STU = re.compile(r"(student|shkol|student)", re.I)
_RE_FR  = re.compile(r"(friend|drug|tovarisch)", re.I)

def _infer_kind(meta: Dict[str, str] | None) -> str:
    if not meta:
        return "neutral"
    if _RE_LAW.search(" ".join(meta.values())):
        return "lawyer"
    if _RE_STU.search(" ".join(meta.values())):
        return "student"
    if _RE_FR.search(" ".join(meta.values())):
        return "friend"
    return meta.get("kind","neutral")

def author_text(intent: str, recipient_kind: Optional[str] = None, meta: Optional[Dict[str, str]] = None, ctx: Optional[Dict] = None) -> str:
    kind = (recipient_kind or _infer_kind(meta) or "neutral").lower()
    draft = render_style(kind, intent, ctx or {})
    # LLM-polirovka (bezopasnaya: off po umolchaniyu)
    refined = suggest_refinement(draft, kind=kind, intent=intent)
    return refined or draft