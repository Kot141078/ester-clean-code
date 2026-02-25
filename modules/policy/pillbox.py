# -*- coding: utf-8 -*-
"""modules/policy/pillbox.py - ochered podtverzhdeniy (“pilyul”): zapros→approve/deny→propusk.

Mosty:
- Yavnyy: (Chelovek ↔ Sistema) ruchnoe podtverzhdenie pered vneshnim/riskovym deystviem.
- Skrytyy #1: (RBAC/Politiki ↔ Bezopasnost) sovmestim s JWT-RBAC: dazhe admin mozhet potrebovat “pilyulyu”.
- Skrytyy #2: (Profile ↔ Audit) kazhdoe sobytie shtampuetsya: kto, chto, kogda, k chemu privyazano.

Zemnoy abzats:
Eto kak “podtverzhdenie operatsii v banke”: bez koda-zayavki deystvie ne proydet; kod zhivet nedolgo i privyazan k konkretnomu telu zaprosa.

# c=a+b"""
from __future__ import annotations
import os, json, time, hashlib, threading, uuid
from typing import Dict, Any, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("PILL_DB","data/policy/pillbox.json")
TTL=int(os.getenv("PILL_TTL_SEC","600") or "600")
AUTO_DENY=(os.getenv("PILL_AUTO_DENY_EXP","true").lower()=="true")
HEADER=os.getenv("PILL_HEADER","X-Pill")

os.makedirs(os.path.dirname(DB), exist_ok=True)
_lock=threading.RLock()

_state={"created":0,"approved":0,"denied":0,"expired":0,"last":0,"last_id":""}

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "policy://pill")
    except Exception:
        pass

def _load()->dict:
    if not os.path.isfile(DB):
        data={"items":{}}
        json.dump(data, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
        return data
    try:
        return json.load(open(DB,"r",encoding="utf-8"))
    except Exception:
        return {"items":{}}

def _save(data: dict)->None:
    json.dump(data, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _sha256(b: bytes)->str:
    return hashlib.sha256(b or b"").hexdigest()

def _is_exp(pill: dict)->bool:
    return int(time.time()) > int(pill.get("t") + pill.get("ttl", TTL))

def _gc(data: dict)->None:
    dirty=False
    for pid,p in list(data.get("items",{}).items()):
        if p.get("status")=="pending" and _is_exp(p):
            if AUTO_DENY:
                p["status"]="denied"; p["reason"]="expired"
            _state["expired"]+=1; dirty=True
    if dirty: _save(data)

def request(method: str, path: str, sha256: str, ttl: Optional[int]=None, note: str|None=None, src_ip: str|None=None)->dict:
    with _lock:
        data=_load(); _gc(data)
        pid=str(uuid.uuid4())
        pill={"id": pid, "status":"pending", "method": method.upper(), "path": path, "sha256": sha256, "ttl": int(ttl or TTL), "t": int(time.time()), "note": note or "", "src_ip": src_ip or ""}
        data["items"][pid]=pill; _save(data)
        _state["created"]+=1; _state["last"]=pill["t"]; _state["last_id"]=pid
    _passport("pill_request", {"id": pid, "method": method, "path": path})
    return {"ok": True, "pill": pill}

def approve(pid: str, approver: str|None=None)->dict:
    with _lock:
        data=_load(); p=data.get("items",{}).get(pid)
        if not p: return {"ok": False, "error":"not_found"}
        if _is_exp(p): 
            if AUTO_DENY: p["status"]="denied"; p["reason"]="expired"; _save(data)
            return {"ok": False, "error":"expired"}
        p["status"]="approved"; p["approver"]=approver or ""
        _save(data); _state["approved"]+=1
    _passport("pill_approve", {"id": pid, "approver": approver or ""})
    return {"ok": True, "pill": p}

def deny(pid: str, reason: str|None=None)->dict:
    with _lock:
        data=_load(); p=data.get("items",{}).get(pid)
        if not p: return {"ok": False, "error":"not_found"}
        p["status"]="denied"; p["reason"]=reason or ""
        _save(data); _state["denied"]+=1
    _passport("pill_deny", {"id": pid, "reason": reason or ""})
    return {"ok": True}

def get(pid: str)->dict:
    data=_load(); p=data.get("items",{}).get(pid)
    if not p: return {"ok": False, "error":"not_found"}
    return {"ok": True, "pill": p}

def list_latest(limit: int=50)->dict:
    data=_load(); it=list((data.get("items") or {}).values())
    it.sort(key=lambda x: x.get("t",0), reverse=True)
    return {"ok": True, "items": it[:max(1, min(limit, 500))]}

def status()->dict:
    return {"ok": True, "ttl": TTL, "header": HEADER, "state": dict(_state)}
# c=a+b