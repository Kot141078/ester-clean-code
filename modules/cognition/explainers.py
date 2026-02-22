# -*- coding: utf-8 -*-
"""
Explainers — metaforicheskie i vizualnye obyasniteli dlya otvetov Ester.

Mosty:
- Yavnyy: (Logika ↔ Ritorika) — sukhoy vyvod prevraschaem v ponyatnoe obyasnenie dlya cheloveka.
- Skrytyy 1: (Memory ↔ Personalizatsiya) — nakladyvaem predpochteniya auditorii/konteksta na shablon obyasneniya.
- Skrytyy 2: (Infoteoriya ↔ Estetika) — szhimaem smysl i upakovuem ego v metaforu/mini-skhemu dlya bystrykh kanalov.

Zemnoy abzats:
Eto «perevodchik s mashinnogo na chelovecheskiy». On beret sukhoy tekst i delaet ego yasnym: prostoe obyasnenie,
analogiyu na zhiteyskom primere i malenkuyu «slovesnuyu diagrammu», esli nuzhno.
"""
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
        return "My reshaem prostuyu zadachu, kak nalit stakan vody, ne raspleskav."
    if audience == "engineer":
        return f"Podumay ob etom kak o nagruzochnom rezistore: {t}. My derzhim tok v bezopasnom diapazone i snimaem shum."
    if audience == "finance":
        return f"Predstav eto kak portfel iz aktivov: {t}. Balansiruem risk i ozhidaemuyu dokhodnost, rebalansiruya po signalam."
    if audience == "cook":
        return f"Eto kak retsept na kukhne: {t}. My doziruem spetsii i derzhim temperaturu, chtoby blyudo bylo stabilnym."
    return f"Prosche govorya: {t}. Kak doroga s razvyazkami — my vybiraem polosu i edem bezopasno i bystro."


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
    """
    Vozvraschaet paket obyasneniy: plain / metaphor / visual.
    """
    aud = _detect_audience(text, audience)
    plain = text.strip() or "Korotkiy otvet: vkhod pustoy."
    metaphor = _make_metaphor_core(plain, aud)
    visual = _make_visual(plain)
    return {"ok": True, "audience": aud, "plain": plain, "metaphor": metaphor, "visual": visual}


# finalnaya stroka
# c=a+b