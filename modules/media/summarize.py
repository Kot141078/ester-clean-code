# -*- coding: utf-8 -*-
"""modules/media/summarize.py - legkiy chastotnyy konspekt (chernovik) po subtitram/transkriptu.

Mosty:
- Yavnyy: (Subtitry ↔ Konspekt) daet “skelet” idey bez LLM.
- Skrytyy #1: (KG ↔ Podskazki) itog mozhno progonyat cherez avtolink.
- Skrytyy #2: (RAG ↔ Navigatsiya) konspekt otpravlyaetsya v RAG fallback.

Zemnoy abzats:
Avtomaticheskaya "ryba" konspekta: razbili na frazy, vybrali zametnye - uzhe est chem dumat dalshe.

# c=a+b"""
from __future__ import annotations
import re
from typing import List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _sentences(text: str)->List[str]:
    s=re.split(r'(?<=[\.\!\?])\s+', text.strip())
    return [x.strip() for x in s if x.strip()]

def draft_notes(text: str, limit: int=12)->dict:
    sents=_sentences(text)
    freq={}
    for s in sents:
        for w in re.findall(r"[A-Za-zA-Yaa-yaEe0-9]+", s.lower()):
            if len(w)<=2: continue
            freq[w]=freq.get(w,0)+1
    scored=[]
    for s in sents:
        score=sum(freq.get(w,0) for w in re.findall(r"[A-Za-zA-Yaa-yaEe0-9]+", s.lower()))
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    bullets=[x[1] for x in scored[:max(3,limit)]]
    return {"ok": True, "bullets": bullets, "n_total": len(sents)}
# c=a+b