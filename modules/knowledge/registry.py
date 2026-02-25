# -*- coding: utf-8 -*-
"""modules/knowledge/registry.py - reestr istochnikov znaniy.

Funktsii:
  add_source(url:str, title:str, meta:dict={}) -> dict
  list_sources(limit=200) -> dict
  get_source(id:str) -> dict
  update_source(id:str, patch:dict) -> dict
  remove_source(id:str) -> dict
  touch_source(id:str, ok:bool, bytes:int=0) -> dict # obnovlyaet metrics
  normalize_url(url) -> str

Dannye khranyatsya v data/knowledge/registry.json (prostoy JSON-registr).

MOSTY:
- Yavnyy: (Istochniki ↔ Memory) - kazhdaya zapis pomnit proiskhozhdenie.
- Skrytyy #1: (Infoteoriya ↔ Dostovernost) — metriki dostupa/oshibok vliyayut na ves.
- Skrytyy #2: (Kibernetika ↔ Ekspluatatsiya) - prozrachnyy reestr → upravlyaemost.

ZEMNOY ABZATs:
Inzhenerno - eto telefonnaya kniga istochnikov s schetchikami. Prakticheski - “profile”,
kotoryy prikladyvaetsya k lyuboy informatsii, chtoby znat, otkuda ona i naskolko nadezhna.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import os, json, time, hashlib, re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.path.join(os.environ.get("ESTER_ROOT", os.getcwd()), "data", "knowledge")
REG = os.path.join(ROOT, "registry.json")
os.makedirs(ROOT, exist_ok=True)

_REG: Dict[str, Dict[str,Any]] = {}

def _save():
    with open(REG, "w", encoding="utf-8") as f:
        json.dump({"ts": int(time.time()), "items": list(_REG.values())}, f, ensure_ascii=False, indent=2)

def _load():
    if not os.path.exists(REG):
        _save(); return
    try:
        with open(REG, "r", encoding="utf-8") as f:
            obj=json.load(f)
            items=obj.get("items",[])
            _REG.clear()
            for s in items:
                _REG[s["id"]]=s
    except Exception:
        pass

_load()

def normalize_url(url:str)->str:
    url=(url or "").strip()
    url=re.sub(r"#.*$","",url)
    url=re.sub(r"/+$","",url)
    return url

def _id(url:str)->str:
    return hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()[:12]

def add_source(url:str, title:str, meta:Dict[str,Any]|None=None)->Dict[str,Any]:
    sid=_id(url)
    if sid in _REG:
        return {"ok":True,"source":_REG[sid],"exists":True}
    s={
        "id": sid,
        "url": normalize_url(url),
        "title": title,
        "meta": meta or {},
        "added_ts": int(time.time()),
        "hits": 0,
        "errors": 0,
        "bytes": 0,
        "last_ts": 0,
        "score": 0.5  # bazovyy doveritelnyy ball (0..1)
    }
    _REG[sid]=s; _save()
    return {"ok":True,"source":s}

def list_sources(limit:int=200)->Dict[str,Any]:
    items=list(_REG.values())
    items.sort(key=lambda s:(-s.get("score",0.5), -s.get("hits",0), s.get("errors",0)))
    return {"ok":True,"items":items[:limit]}

def get_source(sid:str)->Dict[str,Any]:
    return {"ok": sid in _REG, "source": _REG.get(sid)}

def update_source(sid:str, patch:Dict[str,Any])->Dict[str,Any]:
    s=_REG.get(sid)
    if not s: return {"ok":False,"error":"not_found"}
    for k,v in patch.items():
        if k in ("title","meta","score"): s[k]=v
    _save()
    return {"ok":True,"source":s}

def remove_source(sid:str)->Dict[str,Any]:
    if sid in _REG: _REG.pop(sid); _save(); return {"ok":True}
    return {"ok":False,"error":"not_found"}

def touch_source(sid:str, ok:bool, bytes:int=0)->Dict[str,Any]:
    s=_REG.get(sid)
    if not s: return {"ok":False,"error":"not_found"}
    s["last_ts"]=int(time.time())
    s["hits"] += 1 if ok else 0
    s["errors"] += 0 if ok else 1
    s["bytes"] += max(0,int(bytes))
    # prostaya korrektirovka score
    total = s["hits"] + s["errors"]
    err_rate = (s["errors"]/total) if total else 0.0
    s["score"] = round(max(0.1, 0.9 - err_rate*0.8), 3)
    _save()
    return {"ok":True,"source":s}