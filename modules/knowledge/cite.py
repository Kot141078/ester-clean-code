# -*- coding: utf-8 -*-
"""modules/knowledge/cite.py - tsitirovanie i “profile otveta”.

Funktsii:
  build_evidence_pack(record_id:str|None, query:str|None, top_k:int=12) -> dict
  cite_lines(evidence_pack:dict, max_items:int=6) -> dict
  answer_passport(answer_text:str, evidence_pack:dict) -> dict

Name:
- Sobrat dokazatelstva (iz pamyati/reestra), vydat kompaktnye tsitaty i metriki
  uverennosti, chtoby lyuboy otvet imel “profile” proiskhozhdeniya.

MOSTY:
- Yavnyy: (Memory ↔ Dokazatelstva) - kazhdyy vyvod podkreplen ssylkami.
- Skrytyy #1: (Infoteoriya ↔ Szhatie) - kratkie tsitaty vmesto “prostyn”.
- Skrytyy #2: (Kibernetika ↔ Prozrachnost) — obyasnimost → doverie.

ZEMNOY ABZATs:
Inzhenerno - upakovschik: na vkhod evidence, na vykhod kompaktnye ssylki i confident=… .
Prakticheski - eto chtoby lyuboy otvet Ester mozhno bylo proverit i vosstanovit.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import time

from modules.memory import store
from modules.knowledge import quality as Q
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def build_evidence_pack(record_id:str|None=None, query:str|None=None, top_k:int=12)->Dict[str,Any]:
    if record_id:
        r=store._MEM.get(record_id)
        if not r: return {"ok":False,"error":"record_not_found"}
        # vozmem sosedniy kontekst po vektoru
        qv=r.get("vec")
        if qv is None:
            ev=[]
        else:
            ev = [e for e in Q.vec_search(qv, list(store._MEM.values()), top_k=top_k)]  # type: ignore
        # add the entry itself as a core
        if r not in ev: ev.insert(0,r)
    else:
        if not query: return {"ok":False,"error":"no_query"}
        ev=Q.build_evidence(query, top_k).get("evidence",[])
    # pochistim dublikaty
    ded=Q.dedup_records(ev)
    conf=Q.compute_confidence(ded["kept"])
    return {"ok":True,"items":ded["kept"],"dropped":ded["dropped"],"confidence":conf["confidence"],"factors":conf["factors"]}

def cite_lines(pack:Dict[str,Any], max_items:int=6)->Dict[str,Any]:
    cites=[]
    for e in (pack.get("items") or [])[:max_items]:
        meta=e.get("meta") or {}
        src=meta.get("source_id","mem")
        snippet=(e.get("text") or "")[:160].replace("\n"," ").strip()
        cites.append(f"[{src}] {snippet}…")
    return {"ok":True,"citations":cites}

def answer_passport(answer_text:str, evidence_pack:Dict[str,Any])->Dict[str,Any]:
    return {
        "ok":True,
        "ts": int(time.time()),
        "answer": answer_text,
        "confidence": evidence_pack.get("confidence", 0.4),
        "factors": evidence_pack.get("factors", {}),
        "citations": cite_lines(evidence_pack, 6).get("citations", [])
    }