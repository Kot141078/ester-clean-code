# -*- coding: utf-8 -*-
"""
nl/style_profiles.py — stili pisem/soobscheniy dlya raznykh adresatov (RU).

MOSTY:
- (Yavnyy) render_style(kind, intent, ctx) — "lawyer|student|friend|neutral".
- (Skrytyy #1) A/B-slot (`AUTHORING_STYLE_AB=A|B`) — variant formulirovok; bystryy otkat po env.
- (Skrytyy #2) Stels-persona (MSG_STEALTH_PERSONA) vliyaet na vvodnye/ton.

ZEMNOY ABZATs:
Pishem «kak dlya lyudey»: yuristu — sukho i strukturno; shkolniku — prosto; drugu — teplo; po umolchaniyu — neytralno-delovoy.

# c=a+b
"""
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
            f"Proshu rassmotret vopros: {intent}. Kratkie fakty: {ctx.get('facts','—')}. "
            "Nuzhna otsenka riskov i posledovatelnost deystviy. Esli nuzhny dopolnitelnye svedeniya, soobschite."
        )
    else:
        return _wrap(
            f"Dobryy den. Tema: {intent}. Fakty: {ctx.get('facts','net dannykh')}. "
            "Pozhaluysta, ukazhite pravovye riski, veroyatnye sroki i pervyy shag."
        )

def _student(intent: str, ctx: Dict) -> str:
    if _ab() == "A":
        return _wrap(
            f"Davay razberemsya prosto: {intent}. Snachala — ideya, zatem primer, potom korotkaya proverka. "
            "Nachni s shaga 1: obyasni ideyu na bytovom primere."
        )
    else:
        return _wrap(
            f"{intent}. Obyasni «na paltsakh», privedi odin ponyatnyy primer i day malenkoe uprazhnenie iz 3 minut."
        )

def _friend(intent: str, ctx: Dict) -> str:
    if _ab() == "A":
        return _wrap(f"{intent} 🙌 Esli udobno — skazhi paru slov seychas; esli net, napomnyu pozzhe.")
    else:
        return _wrap(f"{intent} — korotko i po-dobromu. Ya ryadom, esli chto.")

def _neutral(intent: str, ctx: Dict) -> str:
    if _ab() == "A":
        return _wrap(f"{intent}. Otvechu kratko i po delu, pri neobkhodimosti — detali posle podtverzhdeniya.")
    else:
        return _wrap(f"{intent}. Snachala kratkiy otvet, zatem — varianty.")

def render_style(kind: str, intent: str, ctx: Dict | None = None) -> str:
    ctx = ctx or {}
    kind = (kind or "neutral").lower()
    if kind == "lawyer": return _lawyer(intent, ctx)
    if kind == "student": return _student(intent, ctx)
    if kind == "friend": return _friend(intent, ctx)
    return _neutral(intent, ctx)