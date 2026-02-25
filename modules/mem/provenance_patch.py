# -*- coding: utf-8 -*-
"""modules/mem/provenance_patch.py ​​- myagkiy hook k menedzheru pamyati: meta.provenance (src, sha256, t_start/t_end, ver).

Mosty:
- Yavnyy: (MemoryManager ↔ Profile) kazhdyy apdeyt pamyati poluchaet profile.
- Skrytyy #1: (Audit ↔ Dedup) sha256 kontenta pomogaet obnaruzhivat dublikaty.
- Skrytyy #2: (Ingest/EntityLink ↔ Skleyka) provenans tyanetsya v KG/gipotezy.

Zemnoy abzats:
Kak stamp on paper: who prines, what vnutri i kogda. Then legche suditsya s khaosom.

# c=a+b"""
from __future__ import annotations
import os, json, time, hashlib
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ENABLE = (os.getenv("PROV_ENABLE","true").lower()=="true")
DB = os.getenv("PROV_DB","data/mem/provenance.jsonl")
os.makedirs(os.path.dirname(DB), exist_ok=True)

_last={"enabled": False, "patched": False, "hits": 0, "last_t": 0}

def _append(obj: dict)->None:
    with open(DB,"a",encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False)+"\n")

def _hash(text: str)->str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

def _patch()->bool:
    global _last
    if _last["patched"]: return True
    try:
        from services.mm_access import get_mm  # type: ignore
        mm=get_mm()
        orig_add=getattr(mm,"add",None)
        orig_update=getattr(mm,"update",None)
        def wrap(fn):
            def inner(*a, **kw):
                t0=time.time()
                res=fn(*a, **kw)
                t1=time.time()
                try:
                    text=kw.get("text") or (a[0] if a else "")
                    src=kw.get("source") or kw.get("src") or "mem://unknown"
                    ver=kw.get("version") or 1
                    prov={"src": str(src), "sha256": _hash(str(text)), "t_start": int(t0), "t_end": int(t1), "ver": int(ver)}
                    _append({"t": int(t1), "prov": prov})
                except Exception:
                    pass
                _last["hits"]+=1; _last["last_t"]=int(t1)
                return res
            return inner
        if callable(orig_add):   mm.add   = wrap(orig_add)   # type: ignore
        if callable(orig_update): mm.update= wrap(orig_update) # type: ignore
        _last["patched"]=True; _last["enabled"]=ENABLE
        return True
    except Exception:
        return False

if ENABLE:
    _patch()

def status()->dict:
    return {"ok": True, "enabled": ENABLE, "patched": _last["patched"], "hits": _last["hits"], "last_t": _last["last_t"]}

def enable(flag: bool)->dict:
    os.environ["PROV_ENABLE"]="true" if flag else "false"
    if flag: _patch()
    return status()
# c=a+b