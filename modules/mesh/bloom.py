# -*- coding: utf-8 -*-
"""
modules/mesh/bloom.py — kompaktnyy Bloom-filtr dlya anonsa vidennykh dokumentov.

Mosty:
- Yavnyy: (P2P ↔ Dublikaty) ne gonyaem povtorno uzhe vidennye id.
- Skrytyy #1: (Set ↔ Ekonomika) ekonomiya trafika/CPU.
- Skrytyy #2: (Nadezhnost ↔ Prostota) JSON-predstavlenie dlya obmena.

Zemnoy abzats:
Kak vizitnitsa: pomnim, s kem uzhe zdorovalis, chtoby ne povtoryatsya.

# c=a+b
"""
from __future__ import annotations
import os, json, math, hashlib
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("BLOOM_DB","data/mesh/bloom.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"m":8192,"k":3,"bits":[0]*8192}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _hashes(s: str, k: int, m: int) -> List[int]:
    h1=int(hashlib.sha256(s.encode("utf-8")).hexdigest(),16)
    h2=int(hashlib.md5(s.encode("utf-8")).hexdigest(),16)
    return [ (h1 + i*h2) % m for i in range(k) ]

def add(id: str) -> Dict[str,Any]:
    j=_load(); m=j["m"]; k=j["k"]; bits=j["bits"]
    for idx in _hashes(id, k, m): bits[idx]=1
    _save(j); return {"ok": True}

def check(id: str) -> Dict[str,Any]:
    j=_load(); m=j["m"]; k=j["k"]; bits=j["bits"]
    seen=all(bits[idx]==1 for idx in _hashes(id,k,m))
    return {"ok": True, "maybe_seen": seen}

def merge(bits: List[int]) -> Dict[str,Any]:
    j=_load()
    if len(bits)!=len(j["bits"]): return {"ok": False, "error":"size_mismatch"}
    j["bits"]=[1 if (a or b) else 0 for a,b in zip(j["bits"], bits)]
    _save(j); return {"ok": True}

def export() -> Dict[str,Any]:
    return _load()
# c=a+b