# -*- coding: utf-8 -*-
"""modules/fleet/core.py - fleet sister: registratsiya uzlov, ochered zadach, naznachenie, otchety.

Mosty:
- Yavnyy: (Raspredelenie ↔ Proizvoditelnost) vybiraem menee zagruzhennyy podkhodyaschiy uzel po tegam.
- Skrytyy #1: (Ostorozhnost ↔ Stoimost) postanovka/ispolnenie prokhodyat cherez CostFence.
- Skrytyy #2: (Zhurnal ↔ Memory) klyuchevye sobytiya kladem v pamyat “s profileom”.

Zemnoy abzats:
Kak dispetcher taksi: know svobodnye mashiny, otdaet poezdki samym podkhodyaschim i sledit za otchetami.

# c=a+b"""
from __future__ import annotations
import os, json, time, hmac, hashlib, random
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

NODES = os.getenv("FLEET_DB_NODES","data/fleet/nodes.json")
TASKS = os.getenv("FLEET_DB_TASKS","data/fleet/tasks.json")
SHARED_KEY = (os.getenv("FLEET_SHARED_KEY","") or "").encode("utf-8")
AB = (os.getenv("FLEET_AB","A") or "A").upper()

def _ensure():
    os.makedirs(os.path.dirname(NODES), exist_ok=True)
    if not os.path.isfile(NODES): json.dump({"nodes":{}}, open(NODES,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(TASKS), exist_ok=True)
    if not os.path.isfile(TASKS): json.dump({"tasks":{}}, open(TASKS,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load_nodes(): _ensure(); return json.load(open(NODES,"r",encoding="utf-8"))
def _save_nodes(j): json.dump(j, open(NODES,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
def _load_tasks(): _ensure(); return json.load(open(TASKS,"r",encoding="utf-8"))
def _save_tasks(j): json.dump(j, open(TASKS,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _mm_log(note:str, meta:Dict[str,Any])->None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, note, meta, source="fleet://core")
    except Exception:
        pass

def _sig_ok(body: str, sig: str)->bool:
    if not SHARED_KEY: return True
    try:
        mac=hmac.new(SHARED_KEY, body.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(mac, sig or "")
    except Exception:
        return False

def register_node(node_id:str, url:str, capacity:Dict[str,Any]|None=None, tags:List[str]|None=None)->Dict[str,Any]:
    j=_load_nodes()
    j["nodes"][node_id]={"url": url, "capacity": dict(capacity or {}), "tags": list(tags or []), "load": {"cpu":0.0}, "ts": int(time.time()), "alive": True}
    _save_nodes(j)
    _mm_log("Flot: zaregistrirovan uzel", {"node": node_id, "url": url})
    return {"ok": True, "node": node_id}

def heartbeat(node_id:str, load:Dict[str,Any]|None=None)->Dict[str,Any]:
    j=_load_nodes(); n=j["nodes"].get(node_id)
    if not n: return {"ok": False, "error":"node_not_found"}
    n["alive"]=True; n["ts"]=int(time.time()); n["load"]=dict(load or {"cpu":0.0})
    _save_nodes(j)
    return {"ok": True}

def submit_task(spec: Dict[str,Any])->Dict[str,Any]:
    # stoimost postanovki
    try:
        from modules.ops.cost_fence import evaluate  # type: ignore
        if not evaluate("fleet_submit", float(spec.get("cost",0.01) or 0.01)).get("allow", True):
            return {"ok": False, "error":"budget_reject"}
    except Exception:
        pass
    t=_load_tasks()
    tid=f"T{int(time.time())}{int(time.time()*1000)%1000:03d}{random.randint(1000,9999)}"
    rec={"id": tid, "spec": spec, "state": "queued", "node": None, "created": int(time.time()), "updated": int(time.time()), "result": None}
    t["tasks"][tid]=rec; _save_tasks(t)
    _mm_log("Fleet: task set", {"task": tid, "kind": spec.get("kind","")})
    return {"ok": True, "id": tid}

def status(tid: str)->Dict[str,Any]:
    t=_load_tasks(); rec=t["tasks"].get(tid)
    return {"ok": bool(rec), "task": rec}

def assign_tick()->Dict[str,Any]:
    if AB!="A":
        return {"ok": True, "note":"AB=B (monitoring), assignment disabled", "done":0}
    nodes=_load_nodes()["nodes"]
    tasks=_load_tasks()
    q=[x for x in tasks["tasks"].values() if x.get("state")=="queued"]
    done=0; skipped=[]
    for rec in q:
        tags=set((rec.get("spec") or {}).get("tags") or [])
        # select live suitable nodes
        cand=[]
        now=int(time.time())
        for nid, n in nodes.items():
            if not n.get("alive"): continue
            if now - int(n.get("ts",0)) > 120: continue
            if tags and not (tags.intersection(set(n.get("tags") or []))):
                continue
            load=float(((n.get("load") or {}).get("cpu") or 0.0))
            cand.append((load, nid))
        if not cand:
            skipped.append(rec["id"]); continue
        cand.sort(key=lambda x: x[0])
        best=cand[0][1]
        rec["node"]=best; rec["state"]="assigned"; rec["updated"]=int(time.time())
        done+=1
    _save_tasks(tasks)
    if done: _mm_log("Fleet: tasks assigned", {"count": done})
    return {"ok": True, "done": done, "skipped": skipped}

def worker_pull(node_id: str)->List[Dict[str,Any]]:
    tasks=_load_tasks()
    out=[]
    for rec in tasks["tasks"].values():
        if rec.get("node")==node_id and rec.get("state")=="assigned":
            out.append(rec)
    return out

def worker_report(node_id: str, tid: str, ok: bool, result: Dict[str,Any])->Dict[str,Any]:
    t=_load_tasks(); rec=t["tasks"].get(tid)
    if not rec or rec.get("node")!=node_id:
        return {"ok": False, "error":"task_not_found_or_not_owned"}
    rec["state"]="done" if ok else "failed"
    rec["result"]=result; rec["updated"]=int(time.time())
    _save_tasks(t)
    _mm_log("Fleet: mission report", {"task": tid, "ok": ok})
    return {"ok": True}
# c=a+b