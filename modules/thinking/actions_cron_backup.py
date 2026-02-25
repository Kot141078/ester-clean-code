# -*- coding: utf-8 -*-
"""modules/thinking/actions_cron_backup.py - eksheny “voli” dlya Cron i Backups.

Mosty:
- Yavnyy: (Mysli ↔ Operkontur) knopki planirovschika i bekapov.
- Skrytyy #1: (Passport ↔ Prozrachnost) upravlyayuschie deystviya vidny.
- Skrytyy #2: (Rules/Survival ↔ Avtonomiya) mozhno veshat na sobytiya/noch.

Zemnoy abzats:
Ester mozhet sama “naznachit nochnye raboty”, zapustit ikh i sdelat sebe kopiyu - privychka vzrosloy sistemy.

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
    def _post(path: str, payload: dict, timeout: int=600):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("cron.status", {}, {"ok":"bool"}, 1, lambda a: _get("/cron/status"))
    register("cron.config", {"enable":"bool","time":"str","tz":"str"}, {"ok":"bool"}, 1, lambda a: _post("/cron/config", {"enable": a.get("enable"), "time": a.get("time"), "tz": a.get("tz")}))
    register("cron.nightly.run", {"dry_run":"bool"}, {"ok":"bool"}, 2, lambda a: _post("/cron/nightly/run", {"dry_run": bool(a.get("dry_run", False))}))
    register("backup.status", {}, {"ok":"bool"}, 1, lambda a: _get("/backup/status"))
    register("backup.snapshot", {"dirs":"list","label":"str"}, {"ok":"bool"}, 2, lambda a: _post("/backup/snapshot", {"dirs": list(a.get("dirs") or []), "label": a.get("label")}))
_reg()
# c=a+b