# -*- coding: utf-8 -*-
"""
modules/sisters/registry.py — reestr «sester» i prostoe raspredelenie zadach po HTTP.

Mosty:
- Yavnyy: (P2P/Set ↔ Operatsii) tsentralizovannyy spisok uzlov i ikh capabilities.
- Skrytyy #1: (Profile ↔ Prozrachnost) vse zadaniya i itogi fiksiruyutsya.
- Skrytyy #2: (Kvoty/Pravila ↔ Ostorozhnost) mozhno sochetat s ingest_guard i rules.

Zemnoy abzats:
Kak dispetcher na sklade: znaet, u kogo kakoy pogruzchik, i otsylaet «ekhat k doku №3».

# c=a+b
"""
from __future__ import annotations
import os, json, time, urllib.request
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("SISTERS_DB","data/p2p/sisters.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"nodes":{}}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def list_nodes()->Dict[str,Any]:
    return _load()

def upsert(name: str, base_url: str, caps: list[str])->Dict[str,Any]:
    j=_load(); N=j.get("nodes") or {}
    N[name]={"base_url": base_url.rstrip("/"), "caps": list(caps or []), "t": int(time.time())}
    j["nodes"]=N; _save(j)
    _passport("sister_upsert", {"name": name, "caps": len(caps or [])})
    return {"ok": True, "node": N[name]}

def _passport(note: str, meta: Dict[str,Any]):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "p2p://sisters")
    except Exception:
        pass

def assign(name: str, path: str, payload: Dict[str,Any], timeout: int=180)->Dict[str,Any]:
    j=_load(); N=j.get("nodes") or {}
    node=N.get(name)
    if not node: return {"ok": False, "error":"not_found"}
    url=node["base_url"] + path
    data=json.dumps(payload or {}).encode("utf-8")
    req=urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j
            rep=_j.loads(r.read().decode("utf-8"))
    except Exception as e:
        rep={"ok": False, "error": str(e)}
    _passport("sister_assign", {"name": name, "path": path, "ok": bool(rep.get("ok",False))})
    return rep
# c=a+b