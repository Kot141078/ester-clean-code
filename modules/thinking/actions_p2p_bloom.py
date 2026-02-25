# -*- coding: utf-8 -*-
"""modules/thinking/actions_p2p_bloom.py - eksheny “voli” dlya P2P Bloom.

Mosty:
- Yavnyy: (Mysli ↔ P2P Dedup) knopki statusa/dobavleniya/proverki/obmena.
- Skrytyy #1: (Profile ↔ Prozrachnost) bazovye ruchki uzhe logiruyut.
- Skrytyy #2: (Planner/Rules ↔ Avtonomiya) ispolzovat v pravilakh pri P2P-sinkhronizatsii.

Zemnoy abzats:
Eti komandy pozvolyayut Ester pered lyubym obmenom bystro ask: “a uzhe videli eto?” — i ne gonyat dublikaty.

# c=a+b"""
from __future__ import annotations
import json, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def _get(path: str, timeout: int=10):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    def _post(path: str, payload: dict, timeout: int=20):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("p2p.bloom.status", {}, {"ok":"bool"}, 1, lambda a: _get("/p2p/bloom/status"))
    register("p2p.bloom.add", {"ids":"list"}, {"ok":"bool"}, 1, lambda a: _post("/p2p/bloom/add", {"ids": list(a.get("ids") or [])}))
    register("p2p.bloom.check", {"ids":"list"}, {"ok":"bool"}, 1, lambda a: _post("/p2p/bloom/check", {"ids": list(a.get("ids") or [])}))
    register("p2p.bloom.export", {}, {"ok":"bool"}, 1, lambda a: _get("/p2p/bloom/export"))
    register("p2p.bloom.import", {"blob":"object"}, {"ok":"bool"}, 1, lambda a: _post("/p2p/bloom/import", dict(a.get("blob") or {})))
    register("p2p.bloom.gossip", {"peer":"str","mode":"str"}, {"ok":"bool"}, 1, lambda a: _post("/p2p/bloom/gossip", {"peer": a.get("peer",""), "mode": a.get("mode","sync")}))
_reg()
# c=a+b