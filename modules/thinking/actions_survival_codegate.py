# -*- coding: utf-8 -*-
"""
modules/thinking/actions_survival_codegate.py — eksheny «voli» dlya bandlov/torrentov/kalitki koda.

Mosty:
- Yavnyy: (Mysli ↔ Rezerv/Bezopasnost) bystrye komandy dlya sokhraneniya/razdachi/proverki.
- Skrytyy #1: (Profile ↔ Prozrachnost) vse deystviya fiksiruyutsya.
- Skrytyy #2: (Cron/Rules ↔ Avtonomiya) udobno v nochnye/sobytiynye protsedury.

Zemnoy abzats:
S etimi knopkami Ester sama delaet «zapasnoy parashyut», delitsya im i ne daet podmenit detali.

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

    register("survival.bundle.create", {"name":"str","include":"list","exclude":"list"}, {"ok":"bool"}, 2,
             lambda a: _post("/survival/bundle/create", {"name": a.get("name","bundle"), "include": list(a.get("include") or []), "exclude": list(a.get("exclude") or [])}))
    register("survival.torrent.create", {"path":"str","trackers":"list"}, {"ok":"bool"}, 2,
             lambda a: _post("/survival/torrent/create", {"path": a.get("path",""), "trackers": list(a.get("trackers") or [])}))
    register("survival.list", {}, {"ok":"bool"}, 1,
             lambda a: _get("/survival/list"))
    register("codegate.sign", {"path":"str","note":"str"}, {"ok":"bool"}, 1,
             lambda a: _post("/codegate/sign", {"path": a.get("path",""), "note": a.get("note","")}))
    register("codegate.verify", {"path":"str"}, {"ok":"bool"}, 1,
             lambda a: _post("/codegate/verify", {"path": a.get("path","")}))
    register("garage.project.register_secure", {"name":"str"}, {"ok":"bool"}, 1,
             lambda a: _post("/garage/project/register_secure", {"name": a.get("name","")}))
_reg()
# c=a+b