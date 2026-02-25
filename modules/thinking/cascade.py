# -*- coding: utf-8 -*-
"""modules/thinking/cascade.py — kaskadnoe myshlenie Ester:
  Think → Recall → Branch (vetvlenie gipotez) → Plan → Act → Reflect.

Features:
- Vetvlenie gipotez (N putey) s bystrym ranzhirovaniem, soft-stop po limitam.
- Integratsiya s pamyatyu i payplaynami (M17), zapis shagov v timeline/events.
- Anti-petli: zaschita ot beskonechnykh tsiklov; avto-otkat po oshibkam.

A/B-slot:
  ENV ESTER_CASCADE_MODE = "A" | "B"
  A - kompaktnye steps; B - bolee razvernutye (bolshe vetvey i proverok).

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import os, time
from modules.memory import store
from modules.memory.vector import embed, search as vec_search
from modules.memory.events import record_event
from modules.context.thoughts_adapter import record_thought
from modules.thinking import pipelines as TP
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
from modules.thinking import cascade_closed as cc

MAX_BRANCHES_A = 2
MAX_BRANCHES_B = 4
MAX_STEPS = 6

def _mode()->str:
    return os.environ.get("ESTER_CASCADE_MODE","A").upper()

def _now()->int: return int(time.time())

def _rank_branches(goal:str, candidates:List[str])->List[Tuple[str,float]]:
    qv=embed(goal)
    fake=[{"id":f"c{i}","text":c,"vec":embed(c)} for i,c in enumerate(candidates)]
    ranked=vec_search(qv,fake,top_k=len(fake))
    # all_search returns a list of records by relevance
    return [(r["text"], float(i+1)/len(ranked)) for i,r in enumerate(ranked)]

def _branch_hypotheses(goal:str)->List[str]:
    base=[
        f"find existing solutions for: ZZF0Z",
        f"collect restrictions/resources for: ZZF0Z",
        f"split the task into subtasks: ЗЗФ0З",
        f"compare alternatives for: ZZF0Z",
        f"conduct a short experiment for: ZZF0Z"
    ]
    k = MAX_BRANCHES_B if _mode()=="B" else MAX_BRANCHES_A
    return base[:k]

def run_cascade(goal:str, params:Dict[str,Any]|None=None)->Dict[str,Any]:
    """Kaskad Think→Recall→Branch→Plan→Act→Reflect.
    Vozvraschaet strukturirovannyy otchet i pishet sledy v pamyat."""
    params=params or {}
    t0=_now()
    steps=[]
    record_event("cascade","start",True,{"goal":goal})
    record_thought(goal,"start-cascade",True)

    # 1) Think
    steps.append({"stage":"think","msg":f"comprehending the goal: ZZF0Z"})
    # 2) Recall
    recalled = store.query(goal, top_k=12)
    steps.append({"stage":"recall","count":len(recalled)})
    record_event("think","recall",True,{"count":len(recalled)})

    # 3) Branch
    hypos=_branch_hypotheses(goal)
    ranked=_rank_branches(goal, hypos)
    ordered=[h for h,_ in ranked]
    branch_scores = cc.score_branches(goal, ordered, recalled) if cc._v2_enabled() else []
    if cc._v2_enabled() and branch_scores:
        branch_scores_sorted = sorted(branch_scores, key=lambda x: float(x.get("decayed") or 0.0), reverse=True)
        top = branch_scores_sorted[0]["text"]
        for sc in branch_scores_sorted[1:]:
            cc._save_residue(goal, sc["text"], sc)
    else:
        top = ordered[0] if ordered else f"reshit prostym planom: {goal}"
    steps.append({"stage":"branch","candidates": ordered, "scores": branch_scores})

    # 4) Plan (iz luchshey vetki) + fallback na pipelines
    # top already selected above
    plan=[
        {"op":"pipeline","name":"decision_plan","args":{"objective":goal,"options":[goal,"otlozhit","issledovat"]}},
        {"op":"pipeline","name":"analyze_text","args":{"text":top}},
    ]
    steps.append({"stage":"plan","steps":plan})
    record_event("plan","cascade-plan",True,{"len":len(plan)})

    # 5) Act (vypolnit shagi plana)
    acts=[]
    max_do = MAX_STEPS
    for i,st in enumerate(plan):
        if max_do<=0: break
        if st["op"]=="pipeline":
            spec=TP.make_spec(st["name"], goal, st.get("args") or {})
            out=TP.run_pipeline(spec)
            acts.append({"i":i,"result":out.get("result",{}),"took_sec":out.get("took_sec",0)})
        else:
            acts.append({"i":i,"result":{"skipped":"unknown op"}})
        max_do-=1
    steps.append({"stage":"act","results":acts})
    record_event("act","cascade-execute",True,{"done":len(acts)})

    # 6) Reflection (result, what to do next)
    # simple squeeze: if the decision_plan was sensitive - reflect
    choice=None
    for a in acts:
        r=a.get("result") or {}
        if r.get("mode")=="decision_plan":
            choice=r.get("choice"); break
    summary=f"The cascade is completed. ZZF0Z"
    steps.append({"stage":"reflect","summary":summary})
    record_thought(goal, summary, True)
    record_event("think","cascade-reflect",True,{"summary":summary})

    # final memory entry for timeline
    memory_add("dream", f"cascade: {goal}", {"summary":summary,"steps":len(steps)})

    t1=_now()
    return {"ok":True,"goal":goal,"took_sec":t1-t0,"steps":steps,"summary":summary}
