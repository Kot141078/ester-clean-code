# -*- coding: utf-8 -*-
"""
modules/mesh/task_queue.py — lokalnaya ochered zadach + protokol claim/heartbeat/finish i pull s pirov.

Mosty:
- Yavnyy: (Raspredelenka ↔ Ispolniteli) obschiy format zadach i bezopasnyy protokol arendy.
- Skrytyy #1: (P2P Bloom ↔ Dedup) vstavka id v filtr, chtoby rezonno obmenivatsya.
- Skrytyy #2: (Backpressure ↔ Vneshnie istochniki) pered pull/setevymi vyzovami mozhno dergat ingest.guard.*.

Zemnoy abzats:
Eto «kniga zakazov»: zayavki prikhodyat, master beret v rabotu, otmechaet puls i sdaet. Sestry mogut podbirat drug drugu zakazy.

# c=a+b
"""
from __future__ import annotations
import os, json, time, urllib.request
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("MESH_DB","data/mesh/tasks.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"node": {}, "tasks": [], "leases": {}, "builds":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def submit(kind: str, payload: Dict[str,Any])->Dict[str,Any]:
    j=_load(); tid=f"T{int(time.time()*1000)}"
    rec={"id": tid, "kind": kind, "payload": payload, "status":"queued","ts": int(time.time())}
    j["tasks"].append(rec); _save(j)
    # Profile (best-effort)
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        get_mm() and upsert_with_passport(get_mm(), "mesh_submit", {"id":tid,"kind":kind}, source="mesh://submit")
    except Exception: pass
    # Dobavim v Bloom — chtoby sosedi ne gonyali dublikat
    try:
        import json as _j, urllib.request as _u
        data=_j.dumps({"ids":[tid]}).encode("utf-8")
        req=_u.Request("http://127.0.0.1:8000/p2p/filter/add", data=data, headers={"Content-Type":"application/json"})
        _u.urlopen(req, timeout=2)
    except Exception: pass
    return {"ok": True, "task": rec}

def claim(worker: str, kinds: List[str], lease_sec: int=300)->Dict[str,Any]:
    j=_load()
    now=int(time.time())
    # istekshie «arendy» vernut v ochered
    for k,v in list(j["leases"].items()):
        if int(v.get("until",0)) <= now:
            for t in j["tasks"]:
                if t["id"]==k and t["status"]=="in_progress":
                    t["status"]="queued"
            j["leases"].pop(k, None)
    # vydat podkhodyaschuyu
    for t in j["tasks"]:
        if t["status"]!="queued": continue
        if kinds and t["kind"] not in kinds: continue
        t["status"]="in_progress"; j["leases"][t["id"]]={"worker": worker, "until": now+int(lease_sec)}
        _save(j)
        return {"ok": True, "task": t, "lease_until": j["leases"][t["id"]]["until"]}
    _save(j); return {"ok": True, "task": None}

def heartbeat(task_id: str, extend_sec: int=300)->Dict[str,Any]:
    j=_load(); l=j["leases"].get(task_id)
    if not l: return {"ok": False, "error":"no_lease"}
    l["until"]=int(time.time())+int(extend_sec); j["leases"][task_id]=l; _save(j)
    return {"ok": True, "lease_until": l["until"]}

def finish(task_id: str, success: bool, result: Dict[str,Any]|None=None)->Dict[str,Any]:
    j=_load()
    for t in j["tasks"]:
        if t["id"]==task_id:
            t["status"]="done" if success else "failed"
            t["result"]= result or {}
            j["leases"].pop(task_id, None)
            _save(j)
            return {"ok": True, "task": t}
    return {"ok": False, "error":"not_found"}

def list_tasks()->Dict[str,Any]:
    j=_load(); return {"ok": True, "items": j.get("tasks",[])}

def pull_from_peers(peers: List[str], max_items: int=20)->Dict[str,Any]:
    """
    Prosteyshiy protokol: GET {peer}/mesh/task/list → vybiraem queued → submit lokalno (id sokhranyaem).
    """
    imported=0; errs=[]
    try:
        # sprosim Bloom, chtoby ne dublirovat
        import json as _j, urllib.request as _u
        for url in peers or []:
            try:
                with _u.urlopen(url.rstrip("/")+"/mesh/task/list", timeout=5) as r:
                    rep=_j.loads(r.read().decode("utf-8"))
                items=[x for x in rep.get("items",[]) if x.get("status")=="queued"][:max_items]
                ids=[x.get("id") for x in items]
                # proverim, kakie uzhe videli
                q=_j.dumps({"ids": ids}).encode("utf-8")
                with _u.urlopen(_u.Request("http://127.0.0.1:8000/p2p/filter/check", data=q, headers={"Content-Type":"application/json"}), timeout=3) as r2:
                    seen=_j.loads(r2.read().decode("utf-8")).get("seen",[])
                for it in items:
                    if it["id"] in seen: continue
                    submit(it["kind"], it.get("payload") or {})
                    imported+=1
            except Exception as e:
                errs.append(str(e))
    except Exception as e:
        errs.append(str(e))
    return {"ok": True, "imported": imported, "errors": errs}
# c=a+b