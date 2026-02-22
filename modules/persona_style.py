# -*- coding: utf-8 -*-
"""
modules/persona_style.py — Vybor «chelovechnogo» stilya dlya pisem i soobscheniy.

Mosty:
- (Yavnyy) Karta audience×intent → stil (ton, registr, struktura).
- (Skrytyy #1) Grays — maksimy kooperatsii: yasnost/umestnost/kratkost.
- (Skrytyy #2) Pul — register adaptation: formalnost/terminy/punktuatsiya po roli adresata.

Zemnoy abzats:
Modul daet vosproizvodimye teksty bez «robota» v golose: korotkie, taktichnye,
vezhlivye. Ne imitiruet cheloveka obmanom — prosto khoroshiy ton.

# c=a+b
"""
from __future__ import annotations
from typing import Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Bazovye profili tona
_BASE = {
    "lawyer": {
        "greeting": "Dobryy den",
        "closing": "S uvazheniem",
        "signature": "—",
        "register": "formal",
        "traits": ["tochnost", "yasnye ssylki na daty/vremya", "bez emotsiy"],
    },
    "student": {
        "greeting": "Privet",
        "closing": "Spasibo",
        "signature": "—",
        "register": "casual",
        "traits": ["korotko", "prostye slova", "druzhelyubno"],
    },
    "friend": {
        "greeting": "Privet",
        "closing": "Obnimayu",
        "signature": "—",
        "register": "warm",
        "traits": ["teplo", "po-chelovecheski", "bez kantselyarita"],
    },
    "business": {
        "greeting": "Zdravstvuyte",
        "closing": "Khoroshego dnya",
        "signature": "—",
        "register": "neutral-formal",
        "traits": ["po delu", "akkuratnye markery", "bez razgovornykh oborotov"],
    },
    "neutral": {
        "greeting": "Zdravstvuyte",
        "closing": "S uvazheniem",
        "signature": "—",
        "register": "neutral",
        "traits": ["kratko", "ponyatno"],
    },
}

# Karta namereniy → struktura
_TEMPL = {
    "letter": "{greeting},\n\n{body}\n\n{closing}\n{signature}",
    "update": "{greeting}, {body} {closing}.",
    "reminder": "{greeting}, napominayu: {body}. {closing}.",
    "apology": "{greeting}, proshu proscheniya: {body}. {closing}.",
    "request": "{greeting}, proshu: {body}. {closing}.",
}

def _clamp_len(s: str, maxlen: int = 2000) -> str:
    s = (s or "").strip()
    return s if len(s) <= maxlen else (s[: maxlen - 1] + "…")

def choose_style(audience: str, intent: str) -> Dict:
    a = (audience or "neutral").lower()
    i = (intent or "update").lower()
    prof = _BASE.get(a, _BASE["neutral"])
    tmpl = _TEMPL.get(i, _TEMPL["update"])
    return {
        "audience": a,
        "intent": i,
        "profile": prof,
        "template": tmpl,
    }

def render_message(audience: str, intent: str, content: str) -> str:
    st = choose_style(audience, intent)
    prof = st["profile"]
    tmpl = st["template"]

    body = _clamp_len(content)
    # Legkie evristiki po registru
    if prof["register"] in ("casual", "warm"):
        # Chut koroche i zhivee
        body = body.replace("neobkhodimo", "nuzhno").replace("osuschestvit", "sdelat")

    msg = tmpl.format(
        greeting=prof["greeting"],
        body=body,
        closing=prof["closing"],
        signature=prof["signature"],
    )
    # Ubiraem lishnie probely pered punktuatsiey i dvoynye perevody strok.
    msg = "\n".join([ln.rstrip() for ln in msg.splitlines()]).strip()
    return msg