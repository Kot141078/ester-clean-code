# -*- coding: utf-8 -*-
"""modules/thinking/actions_pill.py - eksheny “voli” dlya raboty s “pilyulyami” i ikh politikoy.

Mosty:
- Yavnyy: (Mysli ↔ Pillbox/Policy) spisok zayavok, approve/deny, ustanovka patternov.
- Skrytyy #1: (Profile ↔ Prozrachnost) deystviya fiksiruyutsya bazovymi ruchkami.
- Skrytyy #2: (Planner ↔ Avtonomiya) legko vnedrit v stsenarii publikatsiy/platezhey/rassylok.

Zemnoy abzats:
Knopki “posmotri ochered”, “podtverdi” i “izmeni spisok krasnykh knopok”.

# c=a+b"""
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

    register("pill.status", {}, {"ok":"bool"}, 1, lambda a: _get("/pill/status"))
    register("pill.list", {"limit":"number"}, {"ok":"bool"}, 1, lambda a: _get(f"/pill/list?limit={int(a.get('limit',50) or 50)}"))
    register("pill.request", {"method":"str","path":"str","sha256":"str","ttl":"number"}, {"ok":"bool"}, 1, lambda a: _post("/pill/request", {"method": a.get("method","POST"), "path": a.get("path","/"), "sha256": a.get("sha256",""), "ttl": int(a.get("ttl",0) or 0)}))
    register("pill.approve", {"id":"str","approver":"str"}, {"ok":"bool"}, 1, lambda a: _post("/pill/approve", {"id": a.get("id",""), "approver": a.get("approver")}))
    register("pill.deny", {"id":"str","reason":"str"}, {"ok":"bool"}, 1, lambda a: _post("/pill/deny", {"id": a.get("id",""), "reason": a.get("reason")}))
    register("policy.pill.status", {}, {"ok":"bool"}, 1, lambda a: _get("/policy/pill/status"))
    register("policy.pill.config", {"patterns":"list"}, {"ok":"bool"}, 1, lambda a: _post("/policy/pill/config", {"patterns": list(a.get("patterns") or [])}))
_reg()
# c=a+b