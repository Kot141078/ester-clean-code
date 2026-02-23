# -*- coding: utf-8 -*-
"""
U1/services/advisor/planner.py — sostavlenie plana daydzhesta po temam/zabotam.

Mosty:
- Yavnyy: Enderton — plan kak spetsifikatsiya (title/sections), determinirovannaya generatsiya.
- Skrytyy #1: Cover & Thomas — ostavlyaem tolko informativnye zaprosy (unikalnye, bez dubley).
- Skrytyy #2: Ashbi — A/B-slot: B dobavlyaet «sovety» (recommendations), pri oshibke — katbek v A.

Zemnoy abzats (inzheneriya):
Iz spiska tem formiruem sections s filtrami po tegam (rss/inbox). Razmer topa konfiguriruem.
Plan sovmestim s R5/tools/r5_digest_build.py.

# c=a+b
"""
from __future__ import annotations
import os
from typing import Dict, List, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def build_plan_from_topics(topics: List[str], top_per_section: int = 5) -> Dict[str, Any]:
    topics = [t for t in topics if t]
    seen = set()
    uniq: List[str] = []
    for t in topics:
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        uniq.append(t)
    sections = []
    for t in uniq:
        sections.append({"query": t, "tags": ["rss_demo","inbox_demo","rss","inbox"], "top": top_per_section})
    return {"title": "Sovetnik Ester — Daydzhest po zabotam", "sections": sections}