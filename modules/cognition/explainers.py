# -*- coding: utf-8 -*-
"""Explainers - metaforicheskie i vizualnye obyasniteli dlya otvetov Ester.

Mosty:
- Yavnyy: (Logika ↔ Ritorika) - sukhoy vyvod prevraschaem v ponyatnoe obyasnenie dlya cheloveka.
- Skrytyy 1: (Memory ↔ Personalizatsiya) — nakladyvaem predpochteniya auditorii/konteksta na shablon obyasneniya.
- Skrytyy 2: (Infoteoriya ↔ Estetika) — szhimaem smysl i upakovuem ego v metaforu/mini-skhemu dlya bystrykh kanalov.

Zemnoy abzats:
This is “perevodchik s mashinnogo na chelovecheskiy.” On beret sukhoy tekst i delaet ego yasnym: prostoe obyasnenie,
analogiyu na zhiteyskom primere i malenkuyu “slovesnuyu diagrammu”, esli nuzhno."""
from __future__ import annotations

from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


_AUDIENCE_HINTS = {
    "engineer": ("inzhener", "skhema", "signal", "nagruzka", "model"),
    "finance": ("dengi", "dokhod", "risk", "portfel", "dokhodnost"),
    "cook": ("retsept", "ingredient", "vkus", "pech", "gradusy"),
}


def _detect_audience(text: str, audience: str | None) -> str:
    if audience:
        return audience
    t = (text or "").lower()
    for k, words in _AUDIENCE_HINTS.items():
        if any(w in t for w in words):
            return k
    return "general"


def _make_metaphor_core(text: str, audience: str) -> str:
    t = text.strip()
    if not t:
        return "We solve a simple problem, how to pour a glass of water without spilling."
    if audience == "engineer":
        return f"Think of it as a load resistor: ZZF0Z. We keep the current within a safe range and eliminate noise."
    if audience == "finance":
        return f"Think of it as a portfolio of assets: ZZF0Z. We balance risk and expected return by rebalancing according to signals."
    if audience == "cook":
        return f"It's like a recipe in the kitchen: ZZF0Z. We dose the spices and keep the temperature so that the dish is stable."
    return f"Simply put: ZZF0Z. Like a road with junctions, we choose a lane and drive safely and quickly."


def _make_visual(text: str) -> str:
    core = (text or "tsel").strip()[:60]
    return (
        "┌───────────── Explain ─────────────┐\n"
        f"│ Goal : {core:<27}│\n"
        "│ Plan : [Collect]→[Judge]→[Act]    │\n"
        "│ Risk : low←─med→high              │\n"
        "│ Conf: 0..1 (calibrate by history) │\n"
        "└────────────────────────────────────┘"
    )


def explain(text: str, audience: str | None = None) -> Dict[str, Any]:
    """Returns an explanation package: plain/metaphor/visual."""
    aud = _detect_audience(text, audience)
    plain = text.strip() or "Short answer: the input is empty."
    metaphor = _make_metaphor_core(plain, aud)
    visual = _make_visual(plain)
    return {"ok": True, "audience": aud, "plain": plain, "metaphor": metaphor, "visual": visual}


# finalnaya stroka
# c=a+b