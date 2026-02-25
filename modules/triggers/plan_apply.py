# -*- coding: utf-8 -*-
"""modules/triggers/plan_apply.py - primenenie "plana shablonov" partiyami k /triggers/update.

Vkhod:
- plan: [{"index": <int?>, "name": "...", "bbox":{l,t,w,h}, "threshold":0.85, "lang":"eng+rus", ...}, ...]
  * If the index is not specified: create a “pseudo-patch” for manual addition (return in the report as pending_add).
  * If the index is specified: we generate a PATCH for the existing trigger.

Funktsii:
- dry_run(plan, batch=50) -> tolko agregirovannyy spisok PATCH bez vyzova /triggers/update
- apply(plan, batch=50) -> vyzyvaet /triggers/update dlya tekh, u kogo est index; sobiraet report

MOSTY:
- Yavnyy: (Diagnostika ↔ Deystvie) “kandidaty shablonov” → realnye porogi i bbox.
- Skrytyy #1: (Infoteoriya ↔ Prozrachnost) dry-run pokazyvaet, what will be primeneno.
- Skrytyy #2: (Inzheneriya ↔ Sovmestimost) ne dobavlyaet novye triggery — only patchit suschestvuyuschie, ostalnoe — pending_add.

ZEMNOY ABZATs:
Cleany REST; batch-limit zaschischaet ot “dlinnykh” seriy. No problem.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _mk_patch(item: Dict[str, Any]) -> Dict[str, Any] | None:
    idx = item.get("index", None)
    bbox = item.get("bbox") or {}
    thr  = item.get("threshold", None)
    lang = item.get("lang", None)
    new = {}
    if bbox: new["box"] = {"left": int(bbox["left"]), "top": int(bbox["top"]), "width": int(bbox["width"]), "height": int(bbox["height"])}
    if thr is not None: new["threshold"] = float(thr)
    if lang: new["lang"] = str(lang)
    if new and idx is not None:
        return {"index": int(idx), "patch": new}
    return None

def dry_run(plan: List[Dict[str, Any]], batch: int = 50) -> Dict[str, Any]:
    patches = []
    pending_add = []
    for it in plan[:max(1,batch)]:
        p = _mk_patch(it)
        if p: patches.append(p)
        else: pending_add.append(it)
    return {"ok": True, "patches": patches, "pending_add": pending_add, "batch": batch}

def apply(plan: List[Dict[str, Any]], batch: int = 50) -> Dict[str, Any]:
    dr = dry_run(plan, batch=batch)
    results = []
    for p in dr.get("patches", []):
        r = _post("/triggers/update", p)
        results.append({"index": p["index"], "ok": bool(r.get("ok")), "response": r})
    return {"ok": True, "dry_run": dr, "results": results}