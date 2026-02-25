# -*- coding: utf-8 -*-
"""modules/synergy/advisor.py - yadro "sovetnika": lokalnyy raschet podskazok i sygrannosti, plyus delegatnyy rezhim.

MOSTY:
- (Yavnyy) compute_advice(task_text, dims, candidates, team, top_n) → {"advice":[...], "team_bonus":float, "pairwise":{(a,b):w}}
- (Skrytyy #1) A/B-slot: ADVISOR_MODE=A (lokalnyy raschet) or B (popytka REST-vyzova /synergy/assign/advice → avtokatbek na A).
- (Skrytyy #2) Bez pravok orkestratora: vozvraschaem *extras*, kotorye mozhno "podmeshat" v explain-trace or otrenderit v UI.

ZEMNOY ABZATs:
Sovetnik govorit "kto luchshe podkhodit" i "s kem udobnee rabotat", ne lomaya osnovnoy planirovschik - operator vidit prichiny i spokoyno decide.

# c=a+b"""
from __future__ import annotations

import os, json
from typing import Any, Dict, List, Tuple
from roles.store import rank_for_task
from roles.edges import team_affinity, get_edge
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _local_advice(task_text: str, dims: Dict[str, float], candidates: List[str], team: List[str], top_n: int) -> Dict[str, Any]:
    ranked_all = rank_for_task(task_text if task_text else None, dims, top_n=1000)
    if candidates:
        ranked_all = [r for r in ranked_all if r["agent_id"] in set(candidates)]
    if not ranked_all:
        return {"advice": [], "team_bonus": 0.0, "pairwise": {}}

    # normiruem
    max_s = max(r["score"] for r in ranked_all) or 1.0
    advice=[]
    for r in ranked_all:
        norm = r["score"]/max_s
        advice.append({
            "agent_id": r["agent_id"],
            "score": round(r["score"],4),
            "normalized": round(norm,4),
            "labels": r.get("labels",[])[:4],
            "why": [f"profile_match={r['score']:.2f} ({','.join(r.get('labels',[]))})"]
        })
    advice.sort(key=lambda x:x["score"], reverse=True)
    # team bonus and pairs chemistry
    base_team = list(dict.fromkeys(team)) if team else []
    pairwise: Dict[str, float] = {}
    people = sorted(list(set((candidates or []) + base_team)))
    for i in range(len(people)):
        for j in range(i+1,len(people)):
            a,b = people[i], people[j]
            pairwise[f"{a}__{b}"] = float(get_edge(a,b)["weight"])
    t_bonus = float(team_affinity(base_team + ([advice[0]["agent_id"]] if advice else []))) if base_team else 0.0
    return {"advice": advice[:max(1, top_n)], "team_bonus": round(t_bonus,4), "pairwise": pairwise}

def compute_advice(task_text: str = "", dims: Dict[str, float] | None = None,
                   candidates: List[str] | None = None, team: List[str] | None = None, top_n: int = 5) -> Dict[str, Any]:
    """Unifitsirovannyy vkhod; ADVISOR_MODE=B pytaetsya delegirovat v /synergy/assign/advice (esli smontirovan),
    inache - lokalnyy raschet. Vozvraschaemaya struktura prigodna dlya explain-trace i UI."""
    mode = (os.getenv("ADVISOR_MODE","A") or "A").upper()
    dims = dims or {}
    candidates = candidates or []
    team = team or []
    if mode == "B":
        try:
            # local call without HTTP client (if import is available)
            from routes.synergy_assign_advisor import synergy_assign_advice  # type: ignore
            payload = {"task_text": task_text, "dims": dims, "candidates": candidates, "team": team, "top_n": top_n}
            # asinkhronnaya ruchka → vyzovem sinkhronno cherez .__call__ (FastAPI vnutri ne nuzhen dlya logiki)
            # if this doesn’t work, we’ll go to local calculations
            import anyio
            res = anyio.run(lambda: synergy_assign_advice(payload))  # type: ignore
            if hasattr(res, "body"):
                data = json.loads(res.body.decode("utf-8"))
            else:
                data = dict(res)  # in case of a direct dictionary
            if isinstance(data, dict) and data.get("ok"):
                advice = data.get("advice") or []
                return {"advice": advice[:max(1, top_n)], "team_bonus": float(data.get("team_bonus") or 0.0), "pairwise": {}}
        except Exception:
            pass
    # A ili katbek
    return _local_advice(task_text, dims, candidates, team, top_n)
# c=a+b