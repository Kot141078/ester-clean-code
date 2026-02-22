# -*- coding: utf-8 -*-
"""
modules/thinking/actions_ingest_guard.py — eksheny «voli» dlya bektresha i RBAC-statusa.

Mosty:
- Yavnyy: (Mysli ↔ Ingest/RBAC) stsenarii voli mogut proveryat kvoty, soobschat ob oshibkakh i menyat konfig (admin).
- Skrytyy #1: (Planirovschik ↔ Nadezhnost) legko vstavlyaetsya kak «prefiltr» pered vneshnimi vyzovami.
- Skrytyy #2: (Memory ↔ Profile) sobytiya gotovy k zhurnalirovaniyu (vnutrennie khuki).

Zemnoy abzats:
Pered tem kak «idti v set», mozg sprashivaet storozha; esli server rugaetsya — soobschaet ob etom, i potok sam pritikhaet.

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return
    import json, urllib.request

    def _post(path: str, payload: Dict[str,Any], timeout: int=20):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    def _get(path: str, timeout: int=10):
        import urllib.request, json as _j
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            return _j.loads(r.read().decode("utf-8"))

    register("auth.rbac.status", {}, {"ok":"bool"}, 1, lambda args: _get("/auth/rbac/status"))

    register("ingest.guard.check", {"source":"str","cost":"number"}, {"ok":"bool"}, 1,
            lambda args: _post("/ingest/guard/check", {"source": str(args.get("source","default")), "cost": float(args.get("cost",1))}))

    register("ingest.guard.penalize", {"source":"str","code":"number"}, {"ok":"bool"}, 1,
            lambda args: _post("/ingest/guard/penalize", {"source": str(args.get("source","default")), "code": int(args.get("code",500))}))

    register("ingest.guard.status", {}, {"ok":"bool"}, 1, lambda args: _get("/ingest/guard/status"))

    register("ingest.guard.config", {"default_rpm":"number","sources":"object"}, {"ok":"bool"}, 2,
            lambda args: _post("/ingest/guard/config", {"default_rpm": args.get("default_rpm"), "sources": args.get("sources")}, timeout=20))

_reg()
# c=a+b