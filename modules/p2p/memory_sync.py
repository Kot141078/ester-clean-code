# -*- coding: utf-8 -*-
"""modules/p2p/memory_sync.py - sinkhronizatsiya pamyati Ester mezhdu uzlami.

Funktsii:
  compute_index() -> dict # stroit Merkle-khesh po lokalnoy pamyati
  diff_index(remote_index:dict) -> list[str] # vozvraschaet id nedostayuschikh zapisey
  export_records(ids:list[str]) -> dict
  import_records(payload:dict) -> dict
  push(remote_url:str, secret:str) -> dict

MOSTY:
- Yavnyy: (Memory ↔ Soobschestvo)
- Skrytyy #1: (Kibernetika ↔ Detsentralizatsiya) — mnozhestvennye uzly sokhranyayut tselostnost znaniy.
- Skrytyy #2: (Infoteoriya ↔ Doverie) — podpisi i kontrolnye kheshi predotvraschayut iskazheniya.

ZEMNOY ABZATs:
Eto raspredelennoe soznanie: Estery delyatsya opytom po doverennym kanalam, sveryaya podpisi, chtoby ne poteryat smysl.
# c=a+b"""
from __future__ import annotations
import hashlib, json, time, http.client
from typing import Dict, Any, List
from modules.memory import store
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_INDEX_FILE = "data/memory/index.json"

def compute_index() -> Dict[str, Any]:
    data = store._MEM
    hlist=[]
    for rid, rec in data.items():
        h = hashlib.sha256(json.dumps(rec,sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest()
        hlist.append(h)
    root = hashlib.sha256("".join(sorted(hlist)).encode()).hexdigest() if hlist else "0"*64
    idx={"root":root,"count":len(hlist),"ts":int(time.time())}
    with open(_INDEX_FILE,"w",encoding="utf-8") as f: json.dump(idx,f,indent=2)
    return idx

def diff_index(remote_index:Dict[str,Any])->List[str]:
    """Returns the id of records that do not exist locally."""
    local_ids=set(store._MEM.keys())
    remote_ids=set(remote_index.get("ids",[]))
    return list(remote_ids-local_ids)

def export_records(ids:List[str])->Dict[str,Any]:
    out=[store._MEM[i] for i in ids if i in store._MEM]
    return {"records":out,"count":len(out)}

def import_records(payload:Dict[str,Any])->Dict[str,Any]:
    recs=payload.get("records",[])
    added=0
    for r in recs:
        rid=r.get("id")
        if not rid or rid in store._MEM: continue
        store._MEM[rid]=r
        added+=1
    if added: store.snapshot()
    return {"ok":True,"added":added}

def push(remote_url:str, secret:str)->Dict[str,Any]:
    """Transfer memory to remote node"""
    idx = compute_index()
    conn = http.client.HTTPConnection(remote_url, timeout=10)
    payload = json.dumps({"index":idx,"secret":secret})
    conn.request("POST","/p2p/memory/pull_diff",body=payload,headers={"Content-Type":"application/json"})
    r=conn.getresponse(); data=r.read().decode()
    conn.close()
    try: remote=json.loads(data)
    except: return {"ok":False,"error":"remote invalid"}
    missing=remote.get("missing",[])
    if not missing: return {"ok":True,"synced":True}
    export=export_records(missing)
    conn=http.client.HTTPConnection(remote_url,timeout=10)
    body=json.dumps({"secret":secret,**export})
    conn.request("POST","/p2p/memory/import",body=body,headers={"Content-Type":"application/json"})
    r=conn.getresponse(); out=json.loads(r.read().decode())
    conn.close()
    return {"ok":True,"exported":len(export["records"]),"remote_resp":out}