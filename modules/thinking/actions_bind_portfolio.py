# -*- coding: utf-8 -*-
"""
modules/thinking/actions_bind_portfolio.py — eksheny «voli» dlya svyazki Watch→Media i portfolio.

Mosty:
- Yavnyy: (Mysli ↔ Watch/Media/UI) knopki «nastroit/skanirovat» i «sobrat portfolio».
- Skrytyy #1: (Profile ↔ Prozrachnost) deystviya guvernantki vidny.
- Skrytyy #2: (Cron/Rules ↔ Avtonomiya) legko veshat na raspisaniya/sobytiya.

Zemnoy abzats:
Eti knopki pozvolyayut Ester samoy «lovit rybu» (skanirovat, razbirat) i pokazyvat ulov krasivo.

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

    def _get(path: str, timeout: int=30):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    def _post(path: str, payload: dict, timeout: int=180):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("bind.watch_media.status", {}, {"ok":"bool"}, 1, lambda a: _get("/bind/watch-media/status"))
    register("bind.watch_media.config", {"roots":"list","patterns":"list"}, {"ok":"bool"}, 1, lambda a: _post("/bind/watch-media/config", {"roots": list(a.get("roots") or []), "patterns": list(a.get("patterns") or [])}))
    register("bind.watch_media.run", {"roots":"list","patterns":"list"}, {"ok":"bool"}, 1, lambda a: _post("/bind/watch-media/run", {"roots": list(a.get("roots") or []), "patterns": list(a.get("patterns") or [])}))
    register("portfolio.build", {}, {"ok":"bool"}, 1, lambda a: _post("/portfolio/build", {}))
    register("portfolio.view", {}, {"ok":"bool"}, 1, lambda a: _get("/portfolio/view"))
_reg()
# c=a+b