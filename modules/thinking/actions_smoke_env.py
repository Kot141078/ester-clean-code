# -*- coding: utf-8 -*-
"""
modules/thinking/actions_smoke_env.py — eksheny «voli» dlya ENV-dokov i smoke-progona.

Mosty:
- Yavnyy: (Mysli ↔ Diagnostika/Doki) korotkie komandy: pokazat ENV, zapustit smoke.
- Skrytyy #1: (Passport ↔ Prozrachnost) opiraetsya na bazovye ruchki s logirovaniem.
- Skrytyy #2: (Planner/Cron ↔ Avtonomiya) legko povesit na nochnye proverki.

Zemnoy abzats:
Udobnye knopki dlya samoproverki i napominaniy «chto krutitsya v okruzhenii».

# c=a+b
"""
from __future__ import annotations
import json, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def _get(path: str, timeout: int=15):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    def _post(path: str, payload: dict, timeout: int=60):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("docs.env", {}, {"ok":"bool"}, 1, lambda a: _get("/docs/env"))
    register("tools.smoke.run", {"fast":"bool"}, {"ok":"bool"}, 1, lambda a: _post("/tools/smoke/run", {"fast": bool(a.get("fast", False))}))
    register("tools.smoke.status", {}, {"ok":"bool"}, 1, lambda a: _get("/tools/smoke/status"))
    register("tools.smoke.tests", {}, {"ok":"bool"}, 1, lambda a: _get("/tools/smoke/tests"))
_reg()
# c=a+b