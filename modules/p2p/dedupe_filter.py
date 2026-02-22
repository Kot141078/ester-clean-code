# -*- coding: utf-8 -*-
"""
modules/p2p/dedupe_filter.py — Bloom-filtr dlya P2P-anonsov (otsev dubley).

Mosty:
- Yavnyy: (Set ↔ Uzel) khranim otpechatki uzhe vidennykh dokumentov/anonsov.
- Skrytyy #1: (Memory ↔ Profile) operatsii mozhno logirovat (hook gotov).
- Skrytyy #2: (Garazh/Ingest ↔ Proizvoditelnost) menshe gonyaem set i bystree skhodimsya.

Zemnoy abzats:
Eto «setchataya shumovka»: odin raz uvideli id — bolshe ne taschim ego snova, ekonomim trafik i vremya.

# c=a+b
"""
from __future__ import annotations
import os, json, hashlib, math
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("P2P_FILTER_DB","data/p2p/bloom.json")
M =int(os.getenv("P2P_BLOOM_M","1000000") or "1000000")
K =int(os.getenv("P2P_BLOOM_K","7") or "7")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"m": M, "k": K, "bits": ""}, open(DB,"w",encoding="utf-8"))

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"))

def _hashes(s: str, m: int, k: int)->List[int]:
    hs=[]
    seed=hashlib.sha256(s.encode("utf-8")).digest()
    for i in range(k):
        h=hashlib.sha256(seed+bytes([i])).hexdigest()
        hs.append(int(h,16) % m)
    return hs

def _get_bits(j)->bytearray:
    b64=j.get("bits","")
    # prostoe khranenie — kak stroka '0'/'1' (dlya prozrachnosti), bez base64
    if not b64: return bytearray(b"0"*j.get("m",M),)
    return bytearray(b64.encode("ascii"))

def _set_bits(j, bits: bytearray):
    j["bits"]=bits.decode("ascii")

def add(ids: List[str])->Dict[str,Any]:
    j=_load(); m=int(j.get("m",M)); k=int(j.get("k",K))
    bits=_get_bits(j)
    already=[]
    for s in ids or []:
        idxs=_hashes(s,m,k)
        seen=all(bits[i:i+1]==b"1" for i in idxs)
        if seen: already.append(s)
        for i in idxs: bits[i:i+1]=b"1"
    _set_bits(j,bits); _save(j)
    return {"ok": True, "already_seen": already}

def check(ids: List[str])->Dict[str,Any]:
    j=_load(); m=int(j.get("m",M)); k=int(j.get("k",K))
    bits=_get_bits(j)
    seen=[]
    for s in ids or []:
        idxs=_hashes(s,m,k)
        if all(bits[i:i+1]==b"1" for i in idxs):
            seen.append(s)
    return {"ok": True, "seen": seen}

def export_state()->Dict[str,Any]:
    j=_load(); return {"ok": True, "state": j}

def import_state(state: Dict[str,Any])->Dict[str,Any]:
    j=_load()
    if isinstance(state, dict):
        if "m" in state and "k" in state and "bits" in state:
            _save(state); return {"ok": True}
    return {"ok": False, "error":"bad_state"}

def stats()->Dict[str,Any]:
    j=_load(); bits=_get_bits(j)
    ones = sum(1 for b in bits if b==49)  # '1' ASCII 49
    zeros= len(bits) - ones
    return {"ok": True, "m": j.get("m",M), "k": j.get("k",K), "ones": ones, "zeros": zeros}
# c=a+b