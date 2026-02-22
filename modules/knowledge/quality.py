# -*- coding: utf-8 -*-
"""
modules/knowledge/quality.py — kachestvo znaniy: dedup, antimusor, uverennost.

Funktsii:
  dedup_records(records:list) -> dict               # snimet yavnye/semanticheskie dubli
  compute_confidence(evidence:list) -> dict         # agregiruet uverennost (0..1)
  build_evidence(query:str, top_k:int=12) -> dict   # podbiraet dokazatelstva iz pamyati
  attach_provenance(record_id:str, source_id:str)   # privyazyvaet zapis k istochniku

MOSTY:
- Yavnyy: (Kachestvo ↔ Memory) — pered svodkoy/otvetom chistim shum.
- Skrytyy #1: (Infoteoriya ↔ Entropiya) — dedup snizhaet izbytochnost.
- Skrytyy #2: (Kibernetika ↔ Nadezhnost) — uverennost → resheniya safer.

ZEMNOY ABZATs:
Inzhenerno — filtr/otsenschik pered vyvodom. Prakticheski — «proverka na vshivost»:
sobrat opory, snyat povtory, poschitat uverennost i tolko potom govorit.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from collections import defaultdict
import math

from modules.memory import store
from modules.memory.vector import embed, search as vec_search
from modules.knowledge import registry as REG
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _jaccard(a:set,b:set)->float:
    if not a or not b: return 0.0
    return len(a & b) / max(1,len(a|b))

def dedup_records(records:List[Dict[str,Any]], text_key:str="text", jacc:float=0.9, sem:float=0.92)->Dict[str,Any]:
    keep=[]; dropped=[]
    vecs=[]
    for r in records:
        t=(r.get(text_key) or "").strip()
        words=set([w.lower() for w in t.split() if len(w)>2])
        v=r.get("vec")
        dup=False
        # tekstovaya skhozhest
        for i,kr in enumerate(keep):
            kw=set((kr.get(text_key) or "").lower().split())
            if _jaccard(words, kw) >= jacc: dup=True; break
        # semanticheskaya skhozhest po kosinusu
        if not dup and v:
            for kr in keep:
                kv=kr.get("vec")
                if not kv: continue
                # kosinus
                s=sum(x*y for x,y in zip(v,kv))
                na=math.sqrt(sum(x*x for x in v)) or 1e-9
                nb=math.sqrt(sum(y*y for y in kv)) or 1e-9
                cos=float(s/(na*nb))
                if cos >= sem: dup=True; break
        (dropped if dup else keep).append(r)
    return {"ok":True,"kept":keep,"dropped":dropped,"ratio": (len(keep)/(len(records) or 1))}

def build_evidence(query:str, top_k:int=12)->Dict[str,Any]:
    qv=embed(query)
    items=list(store._MEM.values())
    cand=vec_search(qv, items, top_k=top_k)
    # usilim relevantnost faktami/svodkami
    boost=[]
    for r in cand:
        t=r.get("type")
        if t in ("fact","summary","event"): boost.append(r)
    out=dedup_records(boost or cand)
    return {"ok":True,"query":query,"evidence":out["kept"],"dropped":out["dropped"]}

def _src_score(source_id:str)->float:
    s=REG.get_source(source_id).get("source")
    if not s: return 0.5
    return float(s.get("score",0.5))

def compute_confidence(evidence:List[Dict[str,Any]])->Dict[str,Any]:
    """
    Uverennost ~ vzveshennaya summa:
      - plotnost soglasovannykh istochnikov
      - raznoobrazie tipov zapisey
      - kachestvo istochnikov (registry.score)
    (0..1)
    """
    if not evidence:
        return {"ok":True,"confidence":0.2,"factors":{}}
    # raznoobrazie tipov
    types=set([e.get("type") for e in evidence])
    div = min(1.0, len(types)/5.0)
    # istochniki
    srcs=[]
    for e in evidence:
        sid=(e.get("meta") or {}).get("source_id")
        if sid: srcs.append(sid)
    srcs=set(srcs)
    if srcs:
        srcq=sum(_src_score(s) for s in srcs)/len(srcs)
    else:
        srcq=0.5
    # obem
    n=len(evidence); vol = min(1.0, n/10.0)
    # final
    conf = max(0.05, min(1.0, 0.3*div + 0.4*srcq + 0.3*vol))
    return {"ok":True,"confidence":round(conf,3),"factors":{"div":round(div,2),"srcq":round(srcq,2),"vol":round(vol,2)}}

def attach_provenance(record_id:str, source_id:str)->Dict[str,Any]:
    r=store._MEM.get(record_id)
    if not r: return {"ok":False,"error":"not_found"}
    r.setdefault("meta",{})["source_id"]=source_id
    store.snapshot()
    return {"ok":True,"record":r}