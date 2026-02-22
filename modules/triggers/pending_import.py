# -*- coding: utf-8 -*-
"""
modules/triggers/pending_import.py — import «pending_add» v master dobavleniya triggerov.

Naznachenie:
- Prinyat fayl iz pending_export (ili analogichnyy massiv) i podgotovit:
  * dry-run: spisok «gotovykh POST-zaprosov» dlya sozdaniya triggera
  * try_apply: popytka vyzvat /triggers/add (esli v sborke suschestvuet)
  * fallback: eksport spiska POST-zaprosov kak artefakt (dlya ruchnogo primeneniya)

Kontrakty:
- NIChEGO ne menyaem v suschestvuyuschikh ruchkakh; /triggers/add mozhet otsutstvovat → korrektno soobschaem.

MOSTY:
- Yavnyy: (Diagnostika ↔ Deystvie) perenosim pending → «sozdanie» bez syurprizov.
- Skrytyy #1: (Infoteoriya ↔ Prozrachnost) dry-run pokazyvaet tochnye tela zaprosov.
- Skrytyy #2: (Inzheneriya ↔ Sovmestimost) myagkiy fallback na artefakt.

ZEMNOY ABZATs:
Chistyy REST/JSON, offlayn. Esli /triggers/add net — ne delaem nichego s sistemoy.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
import json, time, http.client
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _normalize(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out=[]
    for it in items or []:
        b=it.get("bbox") or {}
        if all(k in b for k in ("left","top","width","height")):
            out.append({
                "name": it.get("name") or "template",
                "box": {"left": int(b["left"]), "top": int(b["top"]), "width": int(b["width"]), "height": int(b["height"])},
                "threshold": float(it.get("threshold", 0.85)),
                "lang": str(it.get("lang","eng+rus")),
                "note": str(it.get("note",""))
            })
    return out

def dry_run(items: List[Dict[str, Any]], batch: int = 50) -> Dict[str, Any]:
    norm=_normalize(items)[:max(1,batch)]
    posts=[{"path":"/triggers/add","payload":x} for x in norm]
    return {"ok": True, "count": len(posts), "posts": posts, "batch": batch}

def _post_local(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        conn=http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
        conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
        r=conn.getresponse(); t=r.read().decode("utf-8","ignore"); conn.close()
        try: return json.loads(t)
        except Exception: return {"ok": False, "raw": t}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def try_apply(items: List[Dict[str, Any]], batch: int = 50) -> Dict[str, Any]:
    dr=dry_run(items, batch=batch)
    results=[]
    supported=True
    for p in dr["posts"]:
        res=_post_local(p["path"], p["payload"])
        if "not found" in str(res).lower() or ("ok" in res and res.get("ok") is False and res.get("error","").lower().find("not")>=0 and res.get("error","").lower().find("support")>=0):
            supported=False
        results.append({"payload": p["payload"], "response": res})
    return {"ok": True, "supported": supported, "results": results, "dry_run": dr}

def export_posts(items: List[Dict[str, Any]], filename: str = "") -> Dict[str, Any]:
    dr=dry_run(items, batch=10**9)
    data={"exported_at": int(time.time()), "kind":"triggers_add_posts", "requests": dr["posts"]}
    body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    name=filename or f"triggers_add_posts_{data['exported_at']}.json"
    return {"ok": True, "filename": name, "bytes": body, "count": len(dr["posts"])}