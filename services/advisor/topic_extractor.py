# -*- coding: utf-8 -*-
"""
U1/services/advisor/topic_extractor.py — izvlechenie tem/zabot iz teksta i/ili kartochek pamyati.

Mosty:
- Yavnyy: Enderton — temy kak predikaty nad tokenami/chastotami; determinirovannaya vyborka top-k.
- Skrytyy #1: Cover & Thomas — berem «signal» (klyuchevye slova/bigrammy), otbrasyvaem «shum» (stop-slova).
- Skrytyy #2: Ashbi — A/B-slot cherez R3_MODE (unigrammy/bigrammy), ustoychivost pri pustykh istochnikakh.

Zemnoy abzats (inzheneriya):
Rabotaet tolko na stdlib i uzhe suschestvuyuschem tokenayzere R3. Umeet brat poslednie kartochki
(tegi: chat, dialog, concern) i obedinyat s peredannym kontekstom. Vozvraschaet spisok poiskovykh zaprosov.

# c=a+b
"""
from __future__ import annotations
import os
import itertools
from typing import List, Dict, Tuple
from services.reco.tokenizer import tokenize  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TRY_CARD_TAGS = {"chat", "dialog", "concern", "note", "inbox"}

def _load_cards_text(limit: int = 2000) -> str:
    # Pytaemsya vytaschit nedavnie kartochki iz pamyati
    try:
        from services.mm_access import get_mm  # type: ignore
        mm = get_mm()
        cards = []
        for m in ("iter_cards", "list_cards", "all_cards", "to_list"):
            if hasattr(mm.cards, m):
                cards = list(getattr(mm.cards, m)())
                break
        # filtruem po tegam
        texts: List[str] = []
        for c in cards[-200:]:
            tags = set((c.get("tags") or [])) if isinstance(c, dict) else set()
            if tags & TRY_CARD_TAGS:
                t = c.get("text") or c.get("content") or c.get("body") or ""
                if t:
                    texts.append(str(t))
        s = "\n".join(texts)
        return s[-limit:]
    except Exception:
        return ""

def _freq(tokens: List[str]) -> Dict[str, int]:
    cnt: Dict[str, int] = {}
    for t in tokens:
        cnt[t] = cnt.get(t, 0) + 1
    return cnt

def _keyphrases(tokens: List[str], top: int = 8) -> List[str]:
    # Prostaya skhlopka: berem samye chastye tokeny (i bigrammy esli est v potoke)
    cnt = _freq(tokens)
    items = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))
    keys = [w for w, _ in items[: max(3, top)]]
    # sobiraem legkie frazy iz sosednikh tokenov, esli prisutstvuyut bigrammy s "_"
    bigs = [w for w in keys if "_" in w]
    return bigs + [w for w in keys if "_" not in w]

def extract_topics(context: str | None = None, top: int = 8) -> List[str]:
    base = (context or "").strip()
    mem = _load_cards_text()
    joined = "\n".join([s for s in (base, mem) if s])
    if not joined:
        return []
    toks = tokenize(joined)
    keys = _keyphrases(toks, top=top)
    # prevraschaem v poiskovye stroki: bigrammy ostavlyaem slitno, unichki — kak est
    queries: List[str] = []
    for w in keys:
        q = " ".join(w.split("_"))
        if q not in queries:
            queries.append(q)
    return queries[:top]