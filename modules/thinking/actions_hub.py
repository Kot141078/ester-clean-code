# -*- coding: utf-8 -*-
"""
modules/thinking/actions_hub.py — eksheny «voli» dlya Hub++.

Mosty:
- Yavnyy: (Mysli ↔ Hub) knopki «otkryt panel» i «poluchit svodku».
- Skrytyy #1: (Passport ↔ Prozrachnost) vyzovy fiksiruyutsya bazovymi ruchkami.
- Skrytyy #2: (Planner ↔ Avtonomiya) svodka mozhet triggerit pravila.

Zemnoy abzats:
Korotkie komandy: zaglyanut na schitovuyu i zabrat JSON-slepok sostoyaniya.

# c=a+b
"""
from __future__ import annotations
import urllib.request, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def _get(path: str, timeout: int=15):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; 
            ct=r.headers.get("Content-Type","")
            if "json" in ct:
                return _j.loads(r.read().decode("utf-8"))
            return {"ok": True, "html": True, "len": len(r.read())}

    register("hub.open", {}, {"ok":"bool"}, 1, lambda a: _get("/app/hub"))
    register("hub.summary", {}, {"ok":"bool"}, 1, lambda a: _get("/app/hub/summary"))
_reg()
# c=a+b