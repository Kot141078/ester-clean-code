# -*- coding: utf-8 -*-
"""
modules/thinking/actions_rules_watch.py — eksheny «voli» dlya Thinking Rules i Folder Watch.

Mosty:
- Yavnyy: (Mysli ↔ Pravila/FS) upravlyaem pravilami i skanerom iz payplayna.
- Skrytyy #1: (Profile ↔ Prozrachnost) lyubye izmeneniya fiksiruyutsya.
- Skrytyy #2: (Cron ↔ Avtonomiya) udobno zvat iz nightly.

Zemnoy abzats:
Knopki «pokazat pravila», «ustanovit», «prognat», «proskanirovat papki» — vse pod rukoy.

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
    def _post(path: str, payload: dict, timeout: int=120):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    # Rules
    register("thinking.rules.list", {}, {"ok":"bool"}, 1, lambda a: _get("/thinking/rules/list"))
    register("thinking.rules.set", {"rules":"list"}, {"ok":"bool"}, 2, lambda a: _post("/thinking/rules/set", {"rules": list(a.get("rules") or [])}))
    register("thinking.rules.evaluate", {"context":"object"}, {"ok":"bool"}, 1, lambda a: _post("/thinking/rules/evaluate", {"context": dict(a.get("context") or {})}))

    # Watch
    register("watch.status", {}, {"ok":"bool"}, 1, lambda a: _get("/watch/status"))
    register("watch.config.set", {"dirs":"list","patterns":"list"}, {"ok":"bool"}, 2, lambda a: _post("/watch/config/set", {"dirs": list(a.get("dirs") or []), "patterns": list(a.get("patterns") or [])}))
    register("watch.scan", {"autoprocess":"bool"}, {"ok":"bool"}, 1, lambda a: _post("/watch/scan", {"autoprocess": bool(a.get("autoprocess", True))}))
_reg()
# c=a+b