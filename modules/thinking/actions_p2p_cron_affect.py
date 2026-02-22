# -*- coding: utf-8 -*-
"""
modules/thinking/actions_p2p_cron_affect.py — eksheny «voli» dlya P2P Bloom, Cron i Affect-Reflect.

Mosty:
- Yavnyy: (Mysli ↔ Set/Nochnye raboty/Refleksiya) daet korotkie komandy dlya vnutrennikh protsessov.
- Skrytyy #1: (Profile ↔ Prozrachnost) soprovozhdaetsya metrikami/shtampami v drugikh modulyakh.
- Skrytyy #2: (SelfCatalog ↔ Opis) poyavyatsya v spiske vozmozhnostey.

Zemnoy abzats:
Komandy «na konchikakh paltsev»: «videli li etot id?», «zapusti nochnoy snapshot», «podumay o samom vazhnom».

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

    # P2P
    register("p2p.filter.add",   {"ids":"list"}, {"ok":"bool"}, 1, lambda a: _post("/p2p/filter/add", {"ids": list(a.get("ids") or [])}))
    register("p2p.filter.check", {"ids":"list"}, {"ok":"bool"}, 1, lambda a: _post("/p2p/filter/check", {"ids": list(a.get("ids") or [])}))
    register("p2p.filter.state", {}, {"ok":"bool"}, 1, lambda a: _get("/p2p/filter/state"))

    # CRON
    register("cron.status", {}, {"ok":"bool"}, 1, lambda a: _get("/cron/status"))
    register("cron.tasks",  {}, {"ok":"bool"}, 1, lambda a: _get("/cron/tasks"))
    register("cron.add",    {"name":"str","rrule":"object","action":"str"}, {"ok":"bool"}, 1, lambda a: _post("/cron/add", {"name": a.get("name","task"), "rrule": dict(a.get("rrule") or {}), "action": a.get("action","")}))
    register("cron.start",  {}, {"ok":"bool"}, 1, lambda a: _post("/cron/start", {}))
    register("cron.stop",   {}, {"ok":"bool"}, 1, lambda a: _post("/cron/stop", {}))
    register("cron.seed_default", {}, {"ok":"bool"}, 1, lambda a: _post("/cron/seed_default", {}))
    register("cron.run_now", {"name":"str"}, {"ok":"bool"}, 1, lambda a: _post("/cron/run_now", {"name": a.get("name","")}))

    # Affect-aware
    register("mem.reflect.affect.short", {"top_k":"number"}, {"ok":"bool"}, 1, lambda a: _post("/mem/reflect/affect/short", {"top_k": int(a.get("top_k",0))}))
_reg()
# c=a+b