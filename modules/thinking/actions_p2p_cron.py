# -*- coding: utf-8 -*-
"""modules/thinking/actions_p2p_cron.py - eksheny "voli" dlya P2P Bloom i Cron.

Mosty:
- Yavnyy: (Mysli ↔ Set/Tekhprotsedury) korotkie komandy dlya obmena filtrami i zapuska reglamentov.
- Skrytyy #1: (Profile ↔ Prozrachnost) vidny iskhody i oshibki.
- Skrytyy #2: (Planirovschik ↔ Avtonomiya) legko vklyuchaetsya v nightly.

Zemnoy abzats:
Nabor knopok: obnovit bloom, vlit chuzhoy, snyat snapshot profilea, obnovit avtodiskaver - i vpered.

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
    def _post(path: str, payload: dict, timeout: int=60):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    # P2P Bloom
    register("p2p.bloom.status", {}, {"ok":"bool"}, 1, lambda a: _get("/p2p/bloom/status"))
    register("p2p.bloom.add", {"ids":"list"}, {"ok":"bool"}, 1, lambda a: _post("/p2p/bloom/add", {"ids": list(a.get("ids") or [])}))
    register("p2p.bloom.export", {}, {"ok":"bool"}, 1, lambda a: _get("/p2p/bloom/export"))
    register("p2p.bloom.merge", {"m":"number","k":"number","bits_hex":"str"}, {"ok":"bool"}, 1, lambda a: _post("/p2p/bloom/merge", {"m": int(a.get("m",0)), "k": int(a.get("k",0)), "bits_hex": a.get("bits_hex","")}))
    register("p2p.bloom.reset", {}, {"ok":"bool"}, 1, lambda a: _post("/p2p/bloom/reset", {}))
    register("p2p.bloom.from_passport", {"limit":"number"}, {"ok":"bool"}, 1, lambda a: _post("/p2p/bloom/from_passport", {"limit": int(a.get("limit",5000))}))

    # Cron
    register("cron.list", {}, {"ok":"bool"}, 1, lambda a: _get("/cron/list"))
    register("cron.plan", {}, {"ok":"bool"}, 1, lambda a: _post("/cron/plan", {}))
    register("cron.run", {"name":"str"}, {"ok":"bool"}, 1, lambda a: _post("/cron/run", {"name": a.get("name","")}))
    register("cron.tick", {}, {"ok":"bool"}, 1, lambda a: _post("/cron/tick", {}))
_reg()
# c=a+b