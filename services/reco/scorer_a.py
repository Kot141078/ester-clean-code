# -*- coding: utf-8 -*-
"""
R3/services/reco/scorer_a.py — fasad A-slota: «postroit indeks» i «otsenit zapros».

Mosty:
- Yavnyy: Enderton — fasad kak kompozitsiya predikatov (build ∧ load ∧ score) s chetkimi usloviyami uspekha.
- Skrytyy #1: Cover & Thomas — ispolzuem TF-IDF kak informatsionno optimalnyy prosteyshiy ves.
- Skrytyy #2: Ashbi — A/B-slot cherez R3_MODE: B vklyuchaet bigrammy/svezhest; pri sboyakh ⇒ avtokatbek v A.

Zemnoy abzats:
Minimalnyy sloy, kotoryy mozhno vyzyvat iz drugikh chastey sistemy ili testov. Nikakikh pobochnykh effektov, krome zapisi JSON indeksa v `data/reco/*`.

# c=a+b
"""
from __future__ import annotations
from typing import List, Dict
from services.reco.tfidf_index import TfidfIndex, build_index  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def reco_build() -> int:
    return build_index()

def reco_score(query: str, top: int = 10, tags: List[str] | None = None) -> List[Dict]:
    idx = TfidfIndex()
    if not idx.load():
        build_index()
        idx.load()
    return idx.score(query, top=top, tags_include=tags or [])