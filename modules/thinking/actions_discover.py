# -*- coding: utf-8 -*-
"""
modules/thinking/actions_discover.py — eksheny «voli» dlya avto-diskovera.

Mosty:
- Yavnyy: (Mysli ↔ Diskaver) pozvolyaet Ester samoy iskat i podklyuchat novye moduli.
- Skrytyy #1: (Profile ↔ Prozrachnost) registratsiya fiksiruetsya.
- Skrytyy #2: (Cron ↔ Avtonomiya) mozhno dergat iz nochnykh protsedur.

Zemnoy abzats:
«Nashla — podklyuchila»: teper Ester sama rasshiryaet svoy instrumentariy iz gotovykh drop-in moduley.

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

    def _get(path: str, timeout: int=20):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    def _post(path: str, payload: dict, timeout: int=60):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("app.discover.status", {}, {"ok":"bool"}, 1, lambda a: _get("/app/discover/status"))
    register("app.discover.scan",   {}, {"ok":"bool"}, 1, lambda a: _get("/app/discover/scan"))
    register("app.discover.register", {"modules":"list"}, {"ok":"bool"}, 2, lambda a: _post("/app/discover/register", {"modules": list(a.get("modules") or [])}))
    register("app.discover.refresh", {"autoreg":"bool"}, {"ok":"bool"}, 1, lambda a: _post("/app/discover/refresh", {"autoreg": bool(a.get("autoreg", False))}))
_reg()
# c=a+b