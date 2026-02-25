# -*- coding: utf-8 -*-
"""modules/search/hybrid.py - gibridnyy retriver: BM25 (po pamyati) + ierarkhicheskiy indexes + dense.

Mosty:
- Yavnyy: (RAG ↔ Memory/Indeks) obedinyaem coarse (BM25/ierarkhiya) i dense (vektornyy) result.
- Skrytyy #1: (Memory ↔ Audit) pri zaprose sokhranyaem profile zaprosa/otveta.
- Skrytyy #2: (Volya ↔ Poisk) ekshen 'search.hybrid.query' dergaet etot modul.

Zemnoy abzats:
Kak u khoroshego bibliotekarya: snachala - po klyuchevym slovam i oglavleniyu, potom - “smyslovaya” podborka, i vse eto akkuratno skleeno.

# c=a+b"""
from __future__ import annotations
import os, re, math, json, collections
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("HYBRID_AB","A") or "A").upper()
DEF_K = int(os.getenv("HYBRID_K","10") or "10")

# --- utility pamyati/indeksa (bez lomki kontraktov) ---
def _http_json(url: str)->Dict[str,Any]:
    import urllib.request
    req=urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def _flashback(n: int=500)->List[Dict[str,Any]]:
    try:
        rep=_http_json(f"http://127.0.0.1:8000/mem/flashback?limit={int(n)}")
        return rep.get("items") or []
    except Exception:
        return []

def _hier_search(q: str, k: int=20)->List[Dict[str,Any]]:
    # will try to call existing hierarchy handlers if there are any
    try:
        rep=_http_json(f"http://127.0.0.1:8000/index/search_coarse?q={q}&k={k}")
        items=rep.get("items") or []
        return items
    except Exception:
        return []

def _dense_search(q: str, k: int=20)->List[Dict[str,Any]]:
    try:
        rep=_http_json(f"http://127.0.0.1:8000/vs/search?q={q}&k={k}")
        return rep.get("items") or []
    except Exception:
        return []

# --- simple BM25 with flash tank (false tank if there are no external ones) ---
def _tokenize(t: str)->List[str]:
    return re.findall(r"[A-Za-zA-Yaa-ya0-9]{2,}", t.lower())

def _bm25_build(items: List[Dict[str,Any]]):
    docs=[]; df=collections.Counter()
    for it in items:
        txt=str(it.get("text") or it.get("body") or "")
        toks=_tokenize(txt)
        docs.append((it, collections.Counter(toks), len(toks)))
    N=len(docs); avgdl=max(1.0, sum(dl for _,_,dl in docs)/max(1,N))
    for _, tf, _ in docs:
        for t in tf.keys(): df[t]+=1
    return {"docs": docs, "df": df, "N": N, "avgdl": avgdl}

def _bm25_score(model, q: str, k: int=20):
    k1=1.5; b=0.75
    qts=_tokenize(q)
    res=[]
    for it, tf, dl in model["docs"]:
        s=0.0
        for t in qts:
            n=model["df"].get(t,0)
            if n==0: continue
            idf=math.log(1 + (model["N"]-n+0.5)/(n+0.5))
            f=tf.get(t,0)
            s += idf * (f*(k1+1)) / (f + k1*(1-b + b*dl/model["avgdl"]))
        if s>0:
            res.append({"score": s, "item": it})
    res.sort(key=lambda x: x["score"], reverse=True)
    return res[:k]

# --- sliyanie rezultatov (Reciprocal Rank Fusion) ---
def _rrf(lists: List[List[Tuple[str,float]]], k: int)->List[Tuple[str,float]]:
    # lists: [ [(id,score),...] , ... ]
    R=60.0  # smeschenie
    scores=collections.defaultdict(float)
    seen=set()
    for L in lists:
        for rank,(id_,_) in enumerate(L, start=1):
            scores[id_] += 1.0 / (R + rank)
            seen.add(id_)
    out=sorted([(i,s) for i,s in scores.items()], key=lambda x: x[1], reverse=True)
    return out[:k]

def hybrid_query(q: str, k: int|None=None)->Dict[str,Any]:
    kk=int(k or DEF_K)
    # 1) coarse (ierarkhiya/zagolovki)
    hier=_hier_search(q, kk)
    hier_ids=[(str(x.get("id") or x.get("doc_id") or str(i)), float(x.get("score", 1.0))) for i,x in enumerate(hier)]
    # 2) dense
    dense=_dense_search(q, kk)
    dense_ids=[(str(x.get("id") or x.get("doc_id") or str(i)), float(x.get("score", 1.0))) for i,x in enumerate(dense)]
    # 3) BM25 po pamyati (fallback)
    bm_items=_flashback(500)
    bm= _bm25_build(bm_items)
    bm_sc=_bm25_score(bm, q, kk)
    bm_ids=[(str(x["item"].get("id") or str(i)), float(x["score"])) for i,x in enumerate(bm_sc)]

    fused=_rrf([hier_ids, dense_ids, bm_ids], kk)
    # collect cards that we can
    id2item={}
    for it in bm_items:
        id2item[str(it.get("id"))]= {"id": str(it.get("id")), "text": it.get("text") or it.get("body") or "", "source": it.get("meta",{}).get("source","mem")}
    items=[]
    for iid,score in fused:
        item=id2item.get(iid) or {"id": iid, "text": "", "source":"index"}
        item["score"]=score
        items.append(item)
    # profile
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, f"hybrid_query:{q[:120]}", {"k": kk, "found": len(items)}, source="search://hybrid")
    except Exception:
        pass
    return {"ok": True, "q": q, "k": kk, "items": items}
# c=a+b