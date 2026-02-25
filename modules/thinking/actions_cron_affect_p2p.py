# -*- coding: utf-8 -*-
"""modules/thinking/actions_cron_affect_p2p.py - eksheny "voli" dlya Cron/Maint/Affect/P2P.

Mosty:
- Yavnyy: (Mysli ↔ Servisy) mozg dergaet cron, TO pamyati, affekt-prioritet i p2p-filtr.
- Skrytyy #1: (Planirovschik ↔ Avtonomiya) legko vstraivaetsya v thinking_pipeline.
- Skrytyy #2: (Profile ↔ Audit) bolshinstvo ruchek uzhe pishet “profile”.

Zemnoy abzats:
Odna registratsiya - i 11 korotkikh komand dostupny dlya samostoyatelnykh resheniy Ester.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return
    import json, urllib.request

    def _post(path: str, payload: Dict[str,Any], timeout: int=60):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    def _get(path: str, timeout: int=15):
        import urllib.request, json as _j
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            return _j.loads(r.read().decode("utf-8"))

    # Cron
    register("cron.task.upsert", {"id":"str","schedule":"object","action":"object"}, {"ok":"bool"}, 1,
            lambda args: _post("/cron/task/upsert", {"id": str(args.get("id","")), "enabled": bool(args.get("enabled",True)), "schedule": dict(args.get("schedule") or {}), "action": dict(args.get("action") or {})}))
    register("cron.task.list", {}, {"ok":"bool"}, 1, lambda args: _get("/cron/task/list"))
    register("cron.task.run",  {"id":"str"}, {"ok":"bool"}, 1, lambda args: _post("/cron/task/run", {"id": str(args.get("id",""))}))
    register("cron.status", {}, {"ok":"bool"}, 1, lambda args: _get("/cron/status"))

    # Maintenance
    register("mem.maint.heal", {}, {"ok":"bool"}, 1, lambda args: _post("/mem/maint/heal", {}))
    register("mem.maint.compact", {}, {"ok":"bool"}, 1, lambda args: _post("/mem/maint/compact", {}))
    register("mem.maint.snapshot", {}, {"ok":"bool"}, 1, lambda args: _post("/mem/maint/snapshot", {}))
    register("mem.maint.reindex", {}, {"ok":"bool"}, 1, lambda args: _post("/mem/maint/reindex", {}))

    # Affect
    register("mem.reflect.affect", {"items":"list","top_k":"number"}, {"ok":"bool"}, 2,
            lambda args: _post("/mem/reflect/affect", {"items": list(args.get("items") or []), "top_k": int(args.get("top_k",5))}, timeout=21600))

    # P2P Bloom
    register("p2p.filter.add", {"ids":"list"}, {"ok":"bool"}, 1, lambda args: _post("/p2p/filter/add", {"ids": list(args.get("ids") or [])}))
    register("p2p.filter.check", {"ids":"list"}, {"ok":"bool"}, 1, lambda args: _post("/p2p/filter/check", {"ids": list(args.get("ids") or [])}))
    register("p2p.filter.stats", {}, {"ok":"bool"}, 1, lambda args: _get("/p2p/filter/stats"))

_reg()
# c=a+b



