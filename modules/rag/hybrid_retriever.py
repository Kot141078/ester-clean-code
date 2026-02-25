# -*- coding: utf-8 -*-
"""modules/rag/hybrid_retriever.py - hybridnyy retriver: coarse (BM25-layt) → dense-stab.

Mosty:
- Yavnyy: (Poisk ↔ Kontent) nakhodit relevantnye fragmenty dazhe pri uzkikh zaprosakh.
- Skrytyy #1: (Memory ↔ Vektory) umeet “pozvat” vektornyy sloy, esli on dostupen; inache rabotaet leksikoy.
- Skrytyy #2: (Mysli ↔ Plan) validnaya tochka vkhoda dlya RAG-payplayna.

Zemnoy abzats:
Kak khoroshiy bibliotekar: snachala beglo po zagolovkam i klyuchevym slovam, zatem - utochnyaet sovpadeniya smyslom (esli est vektora).

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple
import math, re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _tok(s: str)->List[str]:
    return re.findall(r"[A-Za-zA-Yaa-yaEe0-9]{2,}", (s or "").lower())

def _bm25lite_score(q: List[str], d: List[str])->float:
    if not d: return 0.0
    qset=set(q); dset=set(d)
    inter=len(qset & dset)
    # simple formula: intercept fraction with log weight of length
    return inter / math.log2(2+len(dset))

def _dense_try(query: str, docs: List[Dict[str,str]])->List[Tuple[str,float]]:
    """Best-effort: try the “vector” layer through the optional API/modules; otherwise - 0.
    Returns the list (id, quarrel_dense)."""
    # Stub: there are no external dependencies - we will return the same zeros.
    return [(d["id"], 0.0) for d in docs]

def hybrid_rank(query: str, docs: List[Dict[str,str]], top_k: int=5)->List[Dict[str,Any]]:
    # Coarse
    qtok=_tok(query)
    scored=[]
    for d in docs:
        dtok=_tok(d.get("text",""))
        s=_bm25lite_score(qtok, dtok)
        scored.append({"id": d["id"], "text": d.get("text",""), "coarse": s})
    scored.sort(key=lambda x: x["coarse"], reverse=True)
    # Dense (na verkhney korzine, napr. top 50)
    basket=scored[: min(len(scored), 50)]
    dense=_dense_try(query, [{"id":x["id"], "text": x["text"]} for x in basket])
    dmap={i:s for i,s in dense}
    # Smeshenie
    for x in basket:
        x["dense"]=dmap.get(x["id"], 0.0)
        x["final"]= 0.7*x["coarse"] + 0.3*x["dense"]
    basket.sort(key=lambda x: x["final"], reverse=True)
    return basket[: top_k]
# c=a+b