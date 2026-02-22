# -*- coding: utf-8 -*-
"""
modules/thinking/actions_creator_audio_uploader.py — eksheny «voli» dlya Creator/Drama/Uploader.

Mosty:
- Yavnyy: (Mysli ↔ Tvorchestvo) edinye knopki — ot teksta do media i metadannykh.
- Skrytyy #1: (Passport ↔ Prozrachnost) upravlyayuschie deystviya vidny v zhurnale.
- Skrytyy #2: (Garage/Portfolio ↔ Sinergiya) rezultaty legko podkhvatit drugimi uzlami.

Zemnoy abzats:
Eti eksheny pozvolyayut Ester samoy zapuskat «ideya→rolik→gotovo k publikatsii».

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

    def _post(path: str, payload: dict, timeout: int=180):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("creator.script", {"topic":"str","style":"str","duration":"number"}, {"ok":"bool"}, 1, lambda a: _post("/creator/script", {"topic": a.get("topic",""), "style": a.get("style","shorts"), "duration": int(a.get("duration",60))}))
    register("creator.storyboard", {"script":"str","shots":"number"}, {"ok":"bool"}, 1, lambda a: _post("/creator/storyboard", {"script": a.get("script",""), "shots": int(a.get("shots",0))}))
    register("creator.compose", {"images":"list","out":"str","audio":"str"}, {"ok":"bool"}, 2, lambda a: _post("/creator/compose", {"images": list(a.get("images") or []), "out": a.get("out","data/creator/out/out.mp4"), "audio": a.get("audio","")}))

    register("audio.drama.prepare", {"script":"str","cast":"object"}, {"ok":"bool"}, 1, lambda a: _post("/audio/drama/prepare", {"script": a.get("script",""), "cast": dict(a.get("cast") or {})}))
    register("audio.drama.render", {"lines":"list","out_dir":"str"}, {"ok":"bool"}, 2, lambda a: _post("/audio/drama/render", {"lines": list(a.get("lines") or []), "out_dir": a.get("out_dir","data/creator/drama")}))

    register("uploader.prepare", {"script":"str","platform":"str"}, {"ok":"bool"}, 1, lambda a: _post("/uploader/prepare", {"script": a.get("script",""), "platform": a.get("platform","youtube")}))
_reg()
# c=a+b