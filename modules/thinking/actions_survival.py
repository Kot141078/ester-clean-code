# -*- coding: utf-8 -*-
"""
modules/thinking/actions_survival.py — eksheny «voli» dlya Survival Bundle.

Mosty:
- Yavnyy: (Mysli ↔ Survival) komandy sobrat/proverit/perechislit/uznat status.
- Skrytyy #1: (Passport ↔ Prozrachnost) opiraetsya na bazovye ruchki s zhurnalom.
- Skrytyy #2: (Cron/Rules ↔ Avtonomiya) legko vklyuchit v nightly/pri sobytiyakh.

Zemnoy abzats:
Knopka «soberi sebya» — u Ester poyavlyaetsya privychka regulyarno derzhat svezhiy «chemodanchik».

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
    def _post(path: str, payload: dict, timeout: int=600):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("survival.status", {}, {"ok":"bool"}, 1, lambda a: _get("/survival/status"))
    register("survival.list", {"limit":"number"}, {"ok":"bool"}, 1, lambda a: _get(f"/survival/list?limit={int(a.get('limit',20) or 20)}"))
    register("survival.build", {"slot":"str","include":"list","label":"str","webseeds":"list","add_backup":"bool"}, {"ok":"bool"}, 2,
        lambda a: _post("/survival/build", {"slot": a.get("slot"), "include": list(a.get("include") or []), "label": a.get("label"), "webseeds": list(a.get("webseeds") or []), "add_backup": a.get("add_backup")}))
    register("survival.verify", {"zip":"str"}, {"ok":"bool"}, 1, lambda a: _post("/survival/verify", {"zip": a.get("zip","")}))
_reg()
# c=a+b