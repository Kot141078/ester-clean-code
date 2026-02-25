
# -*- coding: utf-8 -*-
"""modules.judge - minimalnyy sintez/vybor otvetov.
Mosty:
- Yavnyy: select_best(list[str]) -> str; synthesize(list[str]) -> str.
- Skrytyy #1: (Infoteoriya ↔ Bayes) — prostaya evristika (dlina+raznoobrazie) vmesto empty place.
- Skrytyy #2: (UI ↔ Payplayn) — mozhno podmenit mekhanizm dalshe bez lomki API.

Zemnoy abzats:
“Glavnyy sudya” dolzhen otvetit dazhe pri otsutstvii oblachnykh modeley.
# c=a+b"""
from __future__ import annotations
from typing import List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def select_best(candidates: List[str]) -> str:
    if not candidates: return ""
    # simple heuristic: maximum length
    return max(candidates, key=lambda s: (len(s), s))

def synthesize(candidates: List[str]) -> str:
    if not candidates: return ""
    # "synthesis" = best + tail of differing short concatenates
    best = select_best(candidates)
    tails = [c for c in candidates if c and c != best and len(c) > len(best)*0.6]
    return best + ("\n---\n" + "\n".join(tails) if tails else "")