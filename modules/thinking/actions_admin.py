# -*- coding: utf-8 -*-
"""modules/thinking/actions_admin.py - eksheny “voli” dlya Invoker i MM Guard.

Mosty:
- Yavnyy: (Mysli ↔ Adminka) daet korotkie komandy dlya otobrazheniya reestra i audita pamyati.
- Skrytyy #1: (Profile ↔ Audit) sami vyzovy mozhno dopolnitelno logirovat pri zhelanii.
- Skrytyy #2: (UI ↔ Prozrachnost) legko vyvodit v interfeyse.

Zemnoy abzats:
Para komand dlya “posmotret spisok knopok” i “what u nas s dostupom k pamyati”.

# c=a+b"""
from __future__ import annotations
import json, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def _get(path: str, timeout: int=20):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    def _post(path: str, payload: dict, timeout: int=60):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("thinking.actions.list", {}, {"ok":"bool"}, 1, lambda a: _get("/thinking/actions/list"))
    register("thinking.actions.stats", {}, {"ok":"bool"}, 1, lambda a: _get("/thinking/actions/stats"))
    register("thinking.act", {"name":"str","args":"object"}, {"ok":"bool"}, 1, lambda a: _post("/thinking/act", {"name": a.get("name",""), "args": dict(a.get("args") or {})}))
    register("mm.audit.status", {}, {"ok":"bool"}, 1, lambda a: _get("/mm/audit/status"))
    register("mm.audit.flag", {"path":"str","reason":"str"}, {"ok":"bool"}, 1, lambda a: _post("/mm/audit/flag", {"path": a.get("path",""), "reason": a.get("reason","manual_flag")}))
_reg()
# c=a+b