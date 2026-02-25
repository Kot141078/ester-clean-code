# -*- coding: utf-8 -*-
"""nl/style_profiles.py — stili pisem/soobscheniy dlya raznykh adresatov (RU).

MOSTY:
- (Yavnyy) render_style(kind, intent, ctx) - "lawyer|student|friend|neutral".
- (Skrytyy #1) A/B-slot (`AUTHORING_STYLE_AB=A|B`) - variant formulirovok; bystryy otkat po env.
- (Skrytyy #2) Stels-persona (MSG_STEALTH_PERSONA) vliyaet na vvodnye/ton.

ZEMNOY ABZATs:
Pishem “kak dlya lyudey”: yuristu - sukho i strukturno; shkolniku - simple; drugu - warmth; po umolchaniyu — neytralno-delovoy.

# c=a+b"""
from __future__ import annotations

import os
from typing import Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _ab() -> str: return os.getenv("AUTHORING_STYLE_AB","A").upper()
def _persona() -> str: return os.getenv("MSG_STEALTH_PERSONA","gentle")

def _wrap(text: str) -> str:
    p = _persona()
    if p == "gentle":
        return text
    if p == "direct":
        return text.replace("pozhaluysta", "").strip()
    return text

def _lawyer(intent: str, ctx: Dict) -> str:
    if _ab() == "A":
        return _wrap(
            f"Please consider the issue: ZZF0Z. Quick Facts: ZZF1ZZ."
            "A risk assessment and sequence of actions are needed. If you need additional information, please let me know."
        )
    else:
        return _wrap(
            f"Good afternoon. Topic: ZZF0Z. Facts: ZZF1ZZ."
            "Please indicate legal risks, likely time frame and first step."
        )

def _student(intent: str, ctx: Dict) -> str:
    if _ab() == "A":
        return _wrap(
            f"Let's get it simple: ZZF0Z. First an idea, then an example, then a short test."
            "Start with step 1: explain the idea using an everyday example."
        )
    else:
        return _wrap(
            f"ZZF0Z. Explain “on your fingers”, give one clear example and give a small exercise of 3 minutes."
        )

def _friend(intent: str, ctx: Dict) -> str:
    if _ab() == "A":
        return _wrap(f"{intent} 🙌 Esli udobno — skazhi paru slov seychas; esli net, napomnyu pozzhe.")
    else:
        return _wrap(f"ZZF0Z - short and kind. I'm nearby if anything happens.")

def _neutral(intent: str, ctx: Dict) -> str:
    if _ab() == "A":
        return _wrap(f"ZZF0Z. I will answer briefly and to the point, if necessary - details after confirmation.")
    else:
        return _wrap(f"ZZF0Z. First the short answer, then the options.")

def render_style(kind: str, intent: str, ctx: Dict | None = None) -> str:
    ctx = ctx or {}
    kind = (kind or "neutral").lower()
    if kind == "lawyer": return _lawyer(intent, ctx)
    if kind == "student": return _student(intent, ctx)
    if kind == "friend": return _friend(intent, ctx)
    return _neutral(intent, ctx)