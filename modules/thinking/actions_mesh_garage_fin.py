# -*- coding: utf-8 -*-
"""
modules/thinking/actions_mesh_garage_fin.py — eksheny «voli» dlya Mesh/Garage/Finance.

Mosty:
- Yavnyy: (Mysli ↔ Proizvodstvo/Uchet) pozvolyaet Ester brat zadaniya, sobirat proekty i uchityvat dengi.
- Skrytyy #1: (Politiki ↔ Ostorozhnost) sovmestimo s /policy/legal/check pered vneshnimi zadachami/publikatsiyami.
- Skrytyy #2: (Planirovschik ↔ Avtonomiya) mozhno stavit regulyarnye sborki i sverki.

Zemnoy abzats:
Nabor korotkikh komand: «kakie u menya stanki», «vozmi rabotu», «soberi sayt», «zapishi dokhod». Vse — ne v teorii, a v dele.

# c=a+b
"""
from __future__ import annotations
import json, urllib.request
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def _get(path: str, timeout: int=20):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    def _post(path: str, payload: Dict[str,Any], timeout: int=60):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    # Mesh
    register("mesh.capabilities", {}, {"ok":"bool"}, 1, lambda a: _get("/mesh/capabilities"))
    register("mesh.task.submit", {"kind":"str","payload":"object"}, {"ok":"bool"}, 1, lambda a: _post("/mesh/task/submit", {"kind": a.get("kind",""), "payload": dict(a.get("payload") or {})}))
    register("mesh.task.claim", {"worker":"str","kinds":"list","lease_sec":"number"}, {"ok":"bool"}, 1, lambda a: _post("/mesh/task/claim", {"worker": a.get("worker","volition"), "kinds": list(a.get("kinds") or []), "lease_sec": int(a.get("lease_sec",300))}))
    register("mesh.task.heartbeat", {"id":"str","extend_sec":"number"}, {"ok":"bool"}, 1, lambda a: _post("/mesh/task/heartbeat", {"id": a.get("id",""), "extend_sec": int(a.get("extend_sec",300))}))
    register("mesh.task.finish", {"id":"str","success":"bool","result":"object"}, {"ok":"bool"}, 1, lambda a: _post("/mesh/task/finish", {"id": a.get("id",""), "success": bool(a.get("success",True)), "result": dict(a.get("result") or {})}))
    register("mesh.task.pull", {"peers":"list","max_items":"number"}, {"ok":"bool"}, 2, lambda a: _post("/mesh/task/pull", {"peers": list(a.get("peers") or []), "max_items": int(a.get("max_items",20))}))
    register("mesh.task.list", {}, {"ok":"bool"}, 1, lambda a: _get("/mesh/task/list"))

    # Garage
    register("garage.project.upsert", {"id":"str","kind":"str","config":"object"}, {"ok":"bool"}, 1, lambda a: _post("/garage/project/upsert", {"id": a.get("id"), "kind": a.get("kind","static_site"), "config": dict(a.get("config") or {})}))
    register("garage.project.list", {}, {"ok":"bool"}, 1, lambda a: _get("/garage/project/list"))
    register("garage.project.build", {"id":"str"}, {"ok":"bool"}, 1, lambda a: _post("/garage/project/build", {"id": a.get("id","")}))
    register("garage.build.status", {}, {"ok":"bool"}, 1, lambda a: _get("/garage/build/status"))

    # Finance
    register("finance.ledger.upsert", {"id":"str","type":"str","source":"str","amount":"number","currency":"str","note":"str"}, {"ok":"bool"}, 1,
            lambda a: _post("/finance/ledger/upsert", {"id": a.get("id"), "type": a.get("type","income"), "source": a.get("source","misc"), "amount": float(a.get("amount",0.0)), "currency": a.get("currency","EUR"), "note": a.get("note","")}))
    register("finance.ledger.list", {}, {"ok":"bool"}, 1, lambda a: _get("/finance/ledger/list"))

_reg()
# c=a+b