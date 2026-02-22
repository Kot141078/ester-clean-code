# -*- coding: utf-8 -*-
"""
modules/sys/codetrust.py — doverie k faylam koda: sha256-«profile», whitelist i karantin.

Mosty:
- Yavnyy: (Kod ↔ Bezopasnost) schitaem sha256, vedem belyy spisok, blokiruem neznakomye.
- Skrytyy #1: (Memory ↔ Profile) logiruem operatsii v obschuyu pamyat.
- Skrytyy #2: (RBAC ↔ Politiki) whitelist dostupen tolko adminam cherez rout.

Zemnoy abzats:
Kak prokhodnaya zavoda: na vkhode proveryaem beydzh (khesh), neznakomykh — v komnatu dosmotra (karantin).

# c=a+b
"""
from __future__ import annotations
import os, json, time, hashlib, shutil
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB  = os.getenv("CODETRUST_DB","data/sys/codetrust.json")
QDIR= os.getenv("CODETRUST_QUARANTINE","data/sys/quarantine")
MODE= (os.getenv("CODETRUST_MODE","strict") or "strict").lower()

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    os.makedirs(QDIR, exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"whitelist": [], "quarantine": []}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def sha256_of(path: str)->str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def whitelist_add(path: str, sha256: str|None=None)->Dict[str,Any]:
    _ensure()
    if not os.path.isfile(path):
        return {"ok": False, "error":"file_not_found"}
    j=_load()
    s=sha256 or sha256_of(path)
    rec={"path": os.path.abspath(path), "sha256": s, "ts": int(time.time())}
    if rec not in j["whitelist"]:
        j["whitelist"].append(rec); _save(j)
    _passport("whitelist_add", rec)
    return {"ok": True, "record": rec}

def is_trusted(path: str)->bool:
    _ensure()
    if not os.path.isfile(path): return False
    j=_load(); s=sha256_of(path); p=os.path.abspath(path)
    for w in j.get("whitelist",[]):
        if w.get("path")==p and w.get("sha256")==s:
            return True
    return MODE!="strict"

def quarantine(path: str, reason: str)->Dict[str,Any]:
    _ensure()
    if not os.path.isfile(path):
        return {"ok": False, "error":"file_not_found"}
    j=_load()
    rec={"path": os.path.abspath(path), "sha256": sha256_of(path), "reason": reason, "ts": int(time.time())}
    # Fayl ne trogaem (ne udalyaem), tolko fiksiruem karantin
    j["quarantine"].append(rec); _save(j)
    _passport("quarantine_mark", rec)
    return {"ok": True, "record": rec}

def status()->Dict[str,Any]:
    j=_load()
    return {"ok": True, "mode": MODE, "whitelist": j.get("whitelist",[]), "quarantine": j.get("quarantine",[])}

def _passport(note:str, meta:Dict[str,Any])->None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, note, meta, source="sys://codetrust")
    except Exception:
        pass
# c=a+b