# -*- coding: utf-8 -*-
"""
modules/thinking/actions_audio_stt.py — eksheny «voli» dlya STT i bindera.

Mosty:
- Yavnyy: (Mysli ↔ STT/Bind) knopki «rasshifrovat fayl» i «oboyti novye media».
- Skrytyy #1: (Profile ↔ Prozrachnost) upravlyayuschie deystviya fiksiruyutsya.
- Skrytyy #2: (RAG/Portfolio ↔ Sinergiya) teksty popadayut v poisk i mogut ispolzovatsya v portfolio.

Zemnoy abzats:
Eti eksheny dayut Ester privychku «snimat tekst» s lyubogo zvuka — i delat eto sama, kogda uvidit novye roliki.

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

    def _post(path: str, payload: dict, timeout: int=300):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("audio.stt.transcribe", {"path":"str","lang":"str","out_dir":"str"}, {"ok":"bool"}, 2, lambda a: _post("/audio/stt/transcribe", {"path": a.get("path",""), "lang": a.get("lang",""), "out_dir": a.get("out_dir","")}))
    register("bind.stt.run", {}, {"ok":"bool"}, 1, lambda a: _post("/bind/stt/run", {}))
_reg()
# c=a+b