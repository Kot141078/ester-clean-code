# -*- coding: utf-8 -*-
"""R6/services/portal/diversity.py - anti-ekho (dedup) i Maximal Marginal Relevance (MMR) dlya raznoobraziya.

Mosty:
- Yavnyy: Cover & Thomas (infoteoriya) - udalyaem izbytochnost (dublikaty) i povyshaem “signal” cherez diversifikatsiyu.
- Skrytyy #1: Enderton (logika) — vse operatsii formalizovany kak predikaty nad mnozhestvami tokenov i schetchikami.
- Skrytyy #2: Ashbi (kibernetika) — A/B-slot: B vklyuchaet MMR i mezhsektsionnyy anti-ekho; pri isklyucheniyakh - katbek v A.

Zemnoy abzats (inzheneriya):
Funktsii prinimayut “flat” elementy daydzhesta (summary/snippet/tags/user/score_a/score_b),
rabotayut tolko na stdlib, ustoychivy k otsutstvuyuschim polyam. Tokenizatsiya - prostaya, bez vneshnikh lib.

# c=a+b"""
from __future__ import annotations
import math
import os
import re
from typing import Dict, Iterable, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_WORD = re.compile(r"[0-9A-Za-zA-Yaa-yaEe_]{2,}", re.UNICODE)

def _tokens(s: str) -> List[str]:
    return [m.group(0).lower() for m in _WORD.finditer(s or "")]

def _tokset(s: str) -> set:
    toks = _tokens(s)
    # easy filtering of stop words (locally)
    stop = {"i","v","na","s","po","the","a","an","of","to","and","or","no","ne","eto","kak","chto","iz","ot"}
    return {t for t in toks if len(t) > 2 and t not in stop}

def jaccard(a: str, b: str) -> float:
    A, B = _tokset(a), _tokset(b)
    if not A or not B:
        return 0.0
    inter = len(A & B)
    union = len(A | B)
    return float(inter) / float(union or 1)

def dedup_items(items: List[dict], threshold: float) -> List[dict]:
    """Removes “similar” elements according to Jaccard (summary + snippet). Maintains the original order."""
    out: List[dict] = []
    seen_texts: List[str] = []
    for it in items:
        txt = (it.get("summary") or "") + " " + (it.get("snippet") or "")
        if any(jaccard(txt, prev) >= threshold for prev in seen_texts):
            continue
        out.append(it)
        seen_texts.append(txt)
    return out

def _sim(a: str, b: str) -> float:
    # cosine on binary bags (via Jaccard as an approximation)
    return jaccard(a, b)

def mmr_select(query: str, items: List[dict], k: int, lam: float) -> List[dict]:
    """Zhadnyy MMR: argmax λ*Sim(q,d) - (1-λ)*max Sim(d, S)
    gde q - stroka zaprosa, d - dokument (summary+snippet), S - uzhe vybrannye."""
    k = max(1, int(k))
    if not items:
        return []
    # Pre-calculation of “query relevance”
    def _text(it: dict) -> str:
        return (it.get("summary") or "") + " " + (it.get("snippet") or "")
    rel = [ _sim(query, _text(it)) for it in items ]
    selected: List[int] = []
    while len(selected) < min(k, len(items)):
        best_i, best_score = None, -1e9
        for i in range(len(items)):
            if i in selected:
                continue
            # penalty = maximum similarity with already selected ones
            penalty = 0.0
            for j in selected:
                penalty = max(penalty, _sim(_text(items[i]), _text(items[j])))
            score = lam * rel[i] - (1.0 - lam) * penalty
            if score > best_score:
                best_score, best_i = score, i
        if best_i is None:
            break
        selected.append(best_i)
    return [items[i] for i in selected]
# c=a+b