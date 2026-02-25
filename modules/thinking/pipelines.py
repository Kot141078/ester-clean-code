# -*- coding: utf-8 -*-
"""modules/thinking/pipelines.py - spetsializirovannye konveyery myshleniya Ester.

Vozmozhnosti:
- JSON-DSL opisaniya payplayna (stages: think/recall/plan/execute/reflect)
- Gotovye shablony: compare_sources, analyze_text, hypothesis_test, decision_plan
- Integratsiya s pamyatyu: kazhdyy etap logiruetsya (context/thoughts_adapter + events)
- Vozvrat strukturirovannogo rezultata (differences/similarities/summary)

MOSTY:
- Yavnyy: (Mysl ↔ Memory) - kazhdyy etap ispolzuet i popolnyaet pamyat.
- Skrytyy #1: (Infoteoriya ↔ Sravnenie) - vektornye profili → skhodstva/razlichiya.
- Skrytyy #2: (Kibernetika ↔ Refleksiya) — Reflect zakryvaet tsikl obratnoy svyazi.

ZEMNOY ABZATs:
Inzhenerno - eto ispolnitel payplaynov s minimalnym DSL i khranilischem sostoyaniy.
Prakticheski - “myslennaya lenta konveyera” dlya zadach: sravni, proanaliziruy, reshi, podvedi itog.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import time, re
from collections import Counter

from modules.memory import store
from modules.memory.vector import embed, search as vec_search
from modules.memory.events import record_event
from modules.context.thoughts_adapter import record_thought
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# ------------------------------
# VSPOMOGATELNYE PROTsEDURY
# ------------------------------

def _ts()->int: return int(time.time())

def _top_terms(texts:List[str], n:int=12)->List[str]:
    words=[]
    for t in texts:
        words += re.findall(r"[A-Za-zA-Yaa-ya0-9]{3,}", (t or "").lower())
    return [w for w,_ in Counter(words).most_common(n)]

def _vec_profile(recs:List[Dict[str,Any]])->List[float]:
    # average embedding (simple “center”)
    vs=[r.get("vec") for r in recs if r.get("vec")]
    if not vs: return []
    L=max(len(v) for v in vs)
    acc=[0.0]*L
    k=0
    for v in vs:
        if not v: continue
        for i,x in enumerate(v):
            acc[i]+=float(x)
        k+=1
    if k==0: return []
    return [x/k for x in acc]

def _cos(a:List[float], b:List[float])->float:
    import math
    if not a or not b: return 0.0
    s=sum(x*y for x,y in zip(a,b))
    na=math.sqrt(sum(x*x for x in a)) or 1e-9
    nb=math.sqrt(sum(y*y for y in b)) or 1e-9
    return float(s/(na*nb))

def _memory_search(keyword:str, top_k:int=50)->List[Dict[str,Any]]:
    # Search for relevant records by key (and semantics, if available)
    items=list(store._MEM.values())
    # grubyy filtr po tekstu
    raw=[r for r in items if keyword.lower() in (r.get("text","").lower())]
    # semanticheskiy dobor
    qv=embed(keyword)
    sem=vec_search(qv, items, top_k=top_k)
    # legkoe obedinenie
    by_id={r["id"]:r for r in raw}
    for r in sem:
        by_id.setdefault(r["id"], r)
    return list(by_id.values())

# ------------------------------
# DSL Execution Core
# ------------------------------

def run_pipeline(spec:Dict[str,Any])->Dict[str,Any]:
    """
    spec: {
      "name": "compare_sources",
      "goal": "...",
      "params": {...},
      "stages": ["think","recall","plan","execute","reflect"]
    }
    """
    t0=_ts()
    name=spec.get("name","pipeline")
    goal=spec.get("goal","")
    params=spec.get("params") or {}
    stages=spec.get("stages") or ["think","recall","plan","execute","reflect"]
    timeline=[]

    record_event("pipeline", name, True, {"goal":goal,"params":params})
    record_thought(goal=f"pipeline:{name}", conclusion="start", success=True)

    ctx={"goal":goal,"params":params,"scratch":{},"result":{}}

    for st in stages:
        if st=="think":
            timeline.append(_stage_think(ctx))
        elif st=="recall":
            timeline.append(_stage_recall(ctx))
        elif st=="plan":
            timeline.append(_stage_plan(ctx))
        elif st=="execute":
            timeline.append(_stage_execute(name, ctx))
        elif st=="reflect":
            timeline.append(_stage_reflect(name, ctx))
        else:
            timeline.append({"stage":st,"ok":False,"msg":"unknown stage"})

    t1=_ts()
    out={"ok":True,"name":name,"goal":goal,"took_sec":t1-t0,"timeline":timeline,"result":ctx["result"]}
    record_thought(goal=f"pipeline:{name}", conclusion="done", success=True)
    record_event("pipeline", name, True, {"done":True,"took":t1-t0})
    # final entry into memory (so that there is a “conveyor history”)
    memory_add("dream", f"pipeline {name}: {ctx['result'].get('summary','gotovo')}",
                     {"goal":goal,"result":ctx["result"],"stage":"final"})
    return out

# ------------------------------
# STAGES (standard handlers)
# ------------------------------

def _stage_think(ctx:Dict[str,Any])->Dict[str,Any]:
    goal=ctx["goal"]
    msg=f"Thinking about the goal: ZZF0Z"
    record_event("think","pipeline_think",True,{"goal":goal})
    record_thought(goal, "init reasoning", True)
    return {"stage":"think","ok":True,"msg":msg}

def _stage_recall(ctx:Dict[str,Any])->Dict[str,Any]:
    # vytaskivaem iz pamyati relevantnyy kontekst
    p=ctx["params"]; goal=ctx["goal"]
    keys=[]
    if p.get("source_a"): keys.append(p["source_a"])
    if p.get("source_b"): keys.append(p["source_b"])
    if not keys: keys.append(goal or "obschaya tema")
    found=[]
    for k in keys:
        found.extend(_memory_search(k, top_k=50))
    ctx["scratch"]["recall"]=found
    record_event("think","pipeline_recall",True,{"count":len(found)})
    return {"stage":"recall","ok":True,"recalled":len(found)}

def _stage_plan(ctx:Dict[str,Any])->Dict[str,Any]:
    name=(ctx.get("params") or {}).get("template") or "compare_sources"
    plan=["extract_terms","build_profiles","compare_profiles","compose_summary"]
    ctx["scratch"]["plan"]=plan
    record_event("plan","pipeline_plan",True,{"steps":len(plan),"template":name})
    return {"stage":"plan","ok":True,"steps":plan}

def _select_records_for_source(recalled:List[Dict[str,Any]], key:str)->List[Dict[str,Any]]:
    key_l=key.lower()
    return [r for r in recalled if key_l in r.get("text","").lower() or key_l in str(r.get("meta","")).lower()]

def _stage_execute(name:str, ctx:Dict[str,Any])->Dict[str,Any]:
    params=ctx["params"]; recalled:List[Dict[str,Any]]=ctx["scratch"].get("recall",[])
    goal=ctx["goal"]

    if name=="compare_sources":
        a=params.get("source_a","istochnik A")
        b=params.get("source_b","istochnik B")
        rec_a=_select_records_for_source(recalled, a)
        rec_b=_select_records_for_source(recalled, b)

        # profili
        prof_a=_vec_profile(rec_a)
        prof_b=_vec_profile(rec_b)
        sim=_cos(prof_a, prof_b)

        terms_a=_top_terms([r.get("text","") for r in rec_a], 12)
        terms_b=_top_terms([r.get("text","") for r in rec_b], 12)

        common=list(sorted(set(terms_a).intersection(terms_b)))[:8]
        unique_a=list(sorted(set(terms_a) - set(terms_b)))[:8]
        unique_b=list(sorted(set(terms_b) - set(terms_a)))[:8]

        summary=(f"Sravnenie '{a}' vs '{b}': skhodstvo={sim:.2f}. "
                 f"Obschie temy: {', '.join(common) if common else '—'}. "
                 f"Unique to ZZF0Z: ZZF1ZZ."
                 f"Unique to ZZF0Z: ZZF1ZZ.")

        ctx["result"]={
            "mode":"compare_sources",
            "a":a,"b":b,
            "similarity":round(sim,3),
            "common":common,
            "unique_a":unique_a,
            "unique_b":unique_b,
            "summary":summary
        }
        record_event("act","compare_sources",True,{"a":a,"b":b,"sim":sim})
        record_thought(goal, f"differences {a} vs {b}", True)
        return {"stage":"execute","ok":True,"compared":True,"sim":sim,"count_a":len(rec_a),"count_b":len(rec_b)}

    elif name=="analyze_text":
        text=params.get("text","")
        terms=_top_terms([text], 15)
        ctx["result"]={"mode":"analyze_text","terms":terms,"summary":"Key themes are extracted."}
        record_event("act","analyze_text",True,{"terms":terms[:5]})
        return {"stage":"execute","ok":True,"terms":terms}

    elif name=="hypothesis_test":
        hypothesis=params.get("hypothesis","")
        evidence=_memory_search(params.get("evidence_key",""), top_k=30)
        verdict="supported" if len(evidence)>=3 else "insufficient"
        ctx["result"]={"mode":"hypothesis_test","hypothesis":hypothesis,"verdict":verdict,"evidence_count":len(evidence)}
        record_event("act","hypothesis_test",True,{"verdict":verdict})
        return {"stage":"execute","ok":True,"verdict":verdict,"evidence":len(evidence)}

    elif name=="decision_plan":
        objective=params.get("objective","")
        options=params.get("options") or []
        # simple heuristic: choose the option that has more “similar” memories
        scored=[]
        for opt in options:
            scored.append((opt, len(_memory_search(opt, top_k=20))))
        scored.sort(key=lambda x:x[1], reverse=True)
        choice=scored[0][0] if scored else (options[0] if options else "")
        ctx["result"]={"mode":"decision_plan","objective":objective,"choice":choice,"scores":scored}
        record_event("act","decision_plan",True,{"choice":choice})
        return {"stage":"execute","ok":True,"choice":choice,"scores":scored}

    else:
        ctx["result"]={"mode":"unknown","summary":"Unknown pattern."}
        record_event("act","unknown_pipeline",False,{"name":name})
        return {"stage":"execute","ok":False,"msg":"unknown template"}

def _stage_reflect(name:str, ctx:Dict[str,Any])->Dict[str,Any]:
    res=ctx.get("result",{})
    msg=res.get("summary","gotovo")
    record_event("think","pipeline_reflect",True,{"name":name})
    record_thought(goal=f"pipeline:{name}", conclusion=msg, success=True)
    # final fixation of the result
    memory_add("summary", f"[{name}] {msg}", {"mode":"pipeline","result":res})
    return {"stage":"reflect","ok":True,"msg":msg}

# ------------------------------
# READY-made Templates (Factors)
# ------------------------------

def builtins()->List[Dict[str,Any]]:
    return [
        {"name":"compare_sources","stages":["think","recall","plan","execute","reflect"]},
        {"name":"analyze_text","stages":["think","plan","execute","reflect"]},
        {"name":"hypothesis_test","stages":["think","recall","plan","execute","reflect"]},
        {"name":"decision_plan","stages":["think","recall","plan","execute","reflect"]},
    ]

def make_spec(name:str, goal:str, params:Dict[str,Any]|None=None)->Dict[str,Any]:
    tpl=next((t for t in builtins() if t["name"]==name), None)
    if not tpl:
        tpl={"name":name,"stages":["think","recall","plan","execute","reflect"]}
    return {"name":name,"goal":goal,"params":params or {}, "stages":tpl["stages"]}