# -*- coding: utf-8 -*-
"""modules/mesh/quorum.py - kvorum resheniy (M-of-N) dlya deystviy v seti sister.

Mosty:
- Yavnyy: (Set ↔ Upravlenie) fiksiruem predlozheniya i golosa.
- Skrytyy #1: (Bezopasnost ↔ Trust) bez kvoruma - net “resheniya”.
- Skrytyy #2: (Inzheneriya ↔ Avtonomiya) legko povesit na guarded_apply / release.

Zemnoy abzats:
Prostaya demokratiya: poka ne nabrali minimum “za” - deystvie ne vypolnyaem.

# c=a+b"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("QUORUM_DB","data/mesh/quorum.json")
DEFAULT_M = int(os.getenv("QUORUM_DEFAULT_M","2") or "2")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"proposals":{}, "votes":{}}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load() -> Dict[str,Any]:
    _ensure(); return json.load(open(DB,"r",encoding="utf-8"))

def _save(j: Dict[str,Any]): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def propose(pid: str, ttl: int, payload: Dict[str,Any]) -> Dict[str,Any]:
    j=_load(); now=int(time.time())
    j["proposals"][pid]={"pid": pid, "ts": now, "ttl": int(ttl), "payload": payload, "m": DEFAULT_M, "decided": None}
    _save(j); return {"ok": True, "pid": pid}

def vote(pid: str, who: str, vote: str) -> Dict[str,Any]:
    j=_load(); now=int(time.time())
    if pid not in j["proposals"]: return {"ok": False, "error":"unknown_pid"}
    j["votes"].setdefault(pid, {})[who]=vote
    # reshaem
    yes=sum(1 for v in j["votes"][pid].values() if v=="yes")
    m=j["proposals"][pid]["m"]; decided = (yes>=m)
    j["proposals"][pid]["decided"] = bool(decided)
    _save(j)
    return {"ok": True, "pid": pid, "yes": yes, "m": m, "decided": decided}

def status() -> Dict[str,Any]:
    j=_load()
    return {"ok": True, "proposals": j.get("proposals",{}), "votes": j.get("votes",{})}
# c=a+b