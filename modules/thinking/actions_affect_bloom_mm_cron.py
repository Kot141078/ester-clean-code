# -*- coding: utf-8 -*-
"""
modules/thinking/actions_affect_bloom_mm_cron.py — eksheny «voli»: MMGate, Affect, Nightly, Bloom.

Mosty:
- Yavnyy: (Mysli ↔ Operatsii) knopki dlya kontrolya pamyati/affekta/nochnykh zadach/P2P.
- Skrytyy #1: (Profile ↔ Prozrachnost) upravlyayuschie deystviya vidny.
- Skrytyy #2: (Rules/Cron ↔ Avtonomiya) tsepochki legko sobirat v Thinking Rules.

Zemnoy abzats:
Nuzhno — proverila chistotu fabriki, otsortirovala «emotsionalnuyu» pamyat, zapustila nochnoy servis i obyavila id v seti.

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

    register("mmgate.status", {}, {"ok":"bool"}, 1, lambda a: _get("/mem/mmgate/status"))
    register("mmgate.scan", {"roots":"list"}, {"ok":"bool"}, 1, lambda a: _post("/mem/mmgate/scan", {"roots": list(a.get("roots") or [])}))

    register("affect.prioritize", {"items":"list","top_k":"number"}, {"ok":"bool"}, 2, lambda a: _post("/mem/affect/prioritize", {"items": list(a.get("items") or []), "top_k": int(a.get("top_k",20))}))

    register("cron.nightly.status", {}, {"ok":"bool"}, 1, lambda a: _get("/cron/nightly/status"))
    register("cron.nightly.run", {}, {"ok":"bool"}, 1, lambda a: _post("/cron/nightly/run", {}))

    register("p2p.bloom.status", {}, {"ok":"bool"}, 1, lambda a: _get("/p2p/bloom/status"))
    register("p2p.bloom.add", {"ids":"list"}, {"ok":"bool"}, 1, lambda a: _post("/p2p/bloom/add", {"ids": list(a.get("ids") or [])}))
    register("p2p.bloom.check", {"ids":"list"}, {"ok":"bool"}, 1, lambda a: _post("/p2p/bloom/check", {"ids": list(a.get("ids") or [])}))
_reg()
# c=a+b