# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.graph.kg_nodes - legkaya prosloyka k knowledge graph.
Mosty:
- Yavnyy: funktsii add_entity()/add_relation()/query() - unifitsirovannyy API nad memory.kg_store.
- Skrytyy #1: (DX ↔ Sovmestimost) - esli memory.kg_store nedostupen, ispolzuem in‑proc folbek (slovar).
- Skrytyy #2: (Memory ↔ Graf) — pin'im minimalnye semantiki uzlov/reber dlya DAG or REST.

Zemnoy abzats:
Count znaniy - eto “svyazki i sustavy” mezhdu faktami. Dazhe bez tyazhelogo dvizhka my mozhem khranit suschnosti i svyazi
v prostoy strukture, chtoby ostalnoy kod ne spotykalsya.
# c=a+b"""
import os
from typing import Dict, Any, List, Optional, Iterable
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = os.getenv("ESTER_GRAPH_AB", "A").upper().strip() or "A"

# --- attempt to link to a real memory.kg_store ---
_store = None
try:
    from memory import kg_store as _kg
    _store = _kg  # expected external module
except Exception:
    _store = None

# --- legkiy folbek in-proc ---
_FALLBACK = {
    "entities": {},   # id -> {"labels":[...], "props":{...}}
    "edges": [],      # {"src":id,"rel":str,"dst":id,"props":{...}}
}

def _fb_add_entity(eid: str, labels: Optional[List[str]]=None, props: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
    labels = labels or []
    props = props or {}
    _FALLBACK["entities"].setdefault(eid, {"labels": [], "props": {}})
    ent = _FALLBACK["entities"][eid]
    # merge
    ent["labels"] = sorted(set(ent["labels"]) | set(labels))
    ent["props"].update(props)
    return {"ok": True, "id": eid, "labels": ent["labels"], "props": ent["props"], "ab": AB}

def _fb_add_relation(src: str, rel: str, dst: str, props: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
    props = props or {}
    _FALLBACK["edges"].append({"src": src, "rel": rel, "dst": dst, "props": props})
    return {"ok": True, "count": len(_FALLBACK["edges"]), "ab": AB}

def _fb_query(label: Optional[str]=None, where: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
    where = where or {}
    res = []
    for eid, e in _FALLBACK["entities"].items():
        if label and label not in e["labels"]:
            continue
        ok = True
        for k, v in where.items():
            if e["props"].get(k) != v:
                ok = False
                break
        if ok:
            res.append({"id": eid, **e})
    return {"ok": True, "items": res, "ab": AB}

# --- publichnyy API ---
def add_entity(eid: str, labels: Optional[List[str]]=None, props: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
    if _store and hasattr(_store, "upsert_entity"):
        try:
            return _store.upsert_entity(eid=eid, labels=labels or [], props=props or {})  # type: ignore
        except TypeError:
            # variatsiya signatury
            return _store.upsert_entity(eid, labels or [], props or {})  # type: ignore
        except Exception:
            pass
    return _fb_add_entity(eid, labels, props)

def add_relation(src: str, rel: str, dst: str, props: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
    if _store and hasattr(_store, "upsert_relation"):
        try:
            return _store.upsert_relation(src=src, rel=rel, dst=dst, props=props or {})  # type: ignore
        except TypeError:
            return _store.upsert_relation(src, rel, dst, props or {})  # type: ignore
        except Exception:
            pass
    return _fb_add_relation(src, rel, dst, props)

def query(label: Optional[str]=None, where: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
    if _store and hasattr(_store, "query"):
        try:
            return _store.query(label=label, where=where or {})  # type: ignore
        except TypeError:
            return _store.query(label, where or {})  # type: ignore
        except Exception:
            pass
    return _fb_query(label, where)