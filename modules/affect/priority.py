# -*- coding: utf-8 -*-
"""modules/affect/priority.py - affect-aware: otsenka intensivnosti i prioriteta zapisi po prostym offlayn-evristikam.

Mosty:
- Yavnyy: (Emotsii ↔ Memory) daem chislovoy “ves” zapisi dlya refleksii/recall.
- Skrytyy #1: (UX ↔ Signaly) bez vneshnikh modeley: vosklitsaniya, kaps, “srochno” i slovar tonalnosti.
- Skrytyy #2: (RAG ↔ Ranzhirovanie) mozhet povyshat schet pri vydache (sm. hybrid).

Zemnoy abzats:
Kak ponyat, chto “vazhno/srochno”, dazhe kogda net interneta i neyrosetey.

# c=a+b"""
from __future__ import annotations
import re, json, os
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AFFECT_AB = (os.getenv("AFFECT_AB","A") or "A").upper()

POS = {"love","great","success","vazhno","lyublyu","khorosho"}
NEG = {"fail","error","urgent","srochno","bolno","opasno","uzhas"}

def score_text(text: str) -> Dict[str,Any]:
    if not text: 
        return {"ok": True, "score": 0.0, "priority": 1.0}
    t = text.strip()
    excl = t.count("!")
    caps = sum(1 for w in re.findall(r"\b[A-ZA-Ya]{3,}\b", t))
    pos = sum(1 for w in POS if w in t.lower())
    neg = sum(1 for w in NEG if w in t.lower())
    score = 0.4*excl + 0.3*caps + 0.2*pos + 0.6*neg
    pr = 1.0 + min(1.0, score/5.0)
    return {"ok": True, "score": score, "priority": pr, "ab": AFFECT_AB}

def policy() -> Dict[str,Any]:
    return {"ok": True, "ab": AFFECT_AB, "desc":"priorities = 1.0 .. 2.0; influences ranking/reflection"}
# c=a+b