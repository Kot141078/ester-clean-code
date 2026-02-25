# -*- coding: utf-8 -*-
"""Brancher - avtonomnoe vetvlenie rassuzhdeniy s sintezom.

Mosty:
- Yavnyy: (Planirovanie ↔ Sudeystvo) — neskolko “versiy mysli” sobirayutsya i sravnivayutsya edinym ranzhirovaniem.
- Skrytyy 1: (Memory ↔ Kognitivnaya estetika) - vozvraschaem i “plain”, i kratkuyu strukturnuyu skhemu plana.
- Skrytyy 2: (Bezopasnaya samo-redaktura ↔ A/B) - B-vetka vklyuchaet bolee agressivnye evristiki, s avtootkatom.

Zemnoy abzats:
Kogda zadacha mutnaya - delaem ne odin otvet, a 2–3 varianta, a potom vybiraem luchshiy po prostym pravilam.
Kak na sovete: kazhdyy vyskazalsya, progolosovali, sostavili obschiy plan po punktam."""
from __future__ import annotations

import os, time
from typing import List, Dict, Any

from modules.meta.ab_warden import ab_switch
from modules.thinking import cascade_closed as cc
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _candidate_fast(task: str) -> Dict[str, Any]:
    return {"name":"fast","text":f"Short answer: ZZF0Z - do the minimum, check, iteration in 24 hours.","score": 0.0}

def _candidate_careful(task: str) -> Dict[str, Any]:
    return {"name":"careful","text":f"A neat step-by-step plan for: ZZF0Z.\n1) Data collection\n2) Risks\n3) Actions\n4) Check","score": 0.0}

def _candidate_tools(task: str) -> Dict[str, Any]:
    return {"name":"tool-aug","text":f"Use the tools: checklist, letter template, progress table - task: ZZF0Z.","score": 0.0}

def _score(c: Dict[str, Any]) -> float:
    # bazovaya evristika, v2 ispolzuet cc.score_branches
    t = c.get("text","")
    s = len(t)/80.0
    if "1)" in t and "2)" in t: s += 0.6
    if "minimum" in t or "minimalnyy" in t: s += 0.2
    return round(s, 3)

def run_branches(task: str, k: int = 3) -> Dict[str, Any]:
    """Returns ZZF0Z.
    Slot A: 3 basic strategies. Slot B: add more “risk” and “expand”."""
    task = (task or "").strip()
    if not task:
        return {"ok": False, "error": "empty_task"}

    with ab_switch("BRANCH") as slot:
        cand = [_candidate_fast(task), _candidate_careful(task), _candidate_tools(task)]
        if slot == "B":
            cand.append({"name":"risk-cut","text":f"Risk profile for: ZZF0Z. We will immediately remove known points of failure and add reserves.", "score":0.0})
            cand.append({"name":"expand","text":f"Horizon expansion: ZZF0Z. Let's consider 2-3 alternative paths and make a Tot-scheme.", "score":0.0})
        if cc._v2_enabled():
            scores = cc.score_branches(task, [c["text"] for c in cand], [])
            scores_sorted = sorted(scores, key=lambda x: float(x.get("decayed") or 0.0), reverse=True)
            best_text = scores_sorted[0]["text"] if scores_sorted else cand[0]["text"]
            for c in cand:
                if c["text"] == best_text:
                    c["score"] = float(next((s["decayed"] for s in scores_sorted if s["text"] == best_text), 0.0))
            # residue for non-picked
            for sc in scores_sorted[1:]:
                cc._save_residue(task, sc["text"], sc)
            pick = next((c for c in cand if c["text"] == best_text), cand[0])
        else:
            for c in cand:
                c["score"] = _score(c)
            pick = sorted(cand, key=lambda x: x["score"], reverse=True)[0]
        sketch = {
            "when": time.time(),
            "task": task[:120],
            "plan": ["Collect","Judge","Act","Review"],
            "picked": pick["name"],
            "slot": slot,
        }
        return {"ok": True, "candidates": cand, "pick": pick, "sketch": sketch}

# finalnaya stroka
# c=a+b
