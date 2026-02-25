# -*- coding: utf-8 -*-
"""modules/thinking/actions_slots_capmap.py - eksheny “voli” dlya A/B-slotov i CapMap.

Mosty:
- Yavnyy: (Mysli ↔ Runtime/Self) knopki “check/pereklyuchit” i “posmotret kartu”.
- Skrytyy #1: (Profile ↔ Prozrachnost) upravlyayuschie deystviya vidny.
- Skrytyy #2: (Rules/Cron ↔ Avtonomiya) legko vstroit v planirovschik.

Zemnoy abzats:
Servisnye knopki: “zdorov li ya?”, “what u menya est?”, “gotov li slot B k vypusku?”.

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

    register("runtime.ab.status", {}, {"ok":"bool"}, 1, lambda a: _get("/runtime/ab/status"))
    register("runtime.ab.health", {"paths":"list"}, {"ok":"bool"}, 1, lambda a: _post("/runtime/ab/health", {"paths": list(a.get("paths") or [])}))
    register("runtime.ab.deploy", {"slot":"str","zip_path":"str"}, {"ok":"bool"}, 2, lambda a: _post("/runtime/ab/deploy", {"slot": a.get("slot",""), "zip_path": a.get("zip_path","")}))
    register("runtime.ab.switch", {"slot":"str","dry_run":"bool","require_health":"bool","paths":"list"}, {"ok":"bool"}, 2, lambda a: _post("/runtime/ab/switch", {"slot": a.get("slot",""), "dry_run": bool(a.get("dry_run",False)), "require_health": bool(a.get("require_health",True)), "paths": list(a.get("paths") or [])}))

    register("self.capmap.json", {}, {"ok":"bool"}, 1, lambda a: _get("/self/capmap"))
    register("self.capmap.html", {}, {"ok":"bool"}, 1, lambda a: _get("/self/capmap/html"))
_reg()
# c=a+b