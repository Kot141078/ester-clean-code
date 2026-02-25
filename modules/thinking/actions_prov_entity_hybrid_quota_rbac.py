# -*- coding: utf-8 -*-
"""modules/thinking/actions_prov_entity_hybrid_quota_rbac.py — eksheny “voli” dlya ostavshikhsya 5 punktov.

Mosty:
- Yavnyy: (Mysli ↔ Memory/RAG/Ingest/Security) upravlyayuschie knopki i zaprosy.
- Skrytyy #1: (Profile ↔ Prozrachnost) vse deystviya vidny.
- Skrytyy #2: (Planner ↔ Avtonomiya) legko sobirat pravila i raspisaniya.

Zemnoy abzats:
Eti eksheny - kak bortovoy pult: shtamp pamyati, yarlyki, umnyy poisk, dozirovannaya podacha i okhrana.

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
    def _post(path: str, payload: dict, timeout: int=120):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("mem.prov.status", {}, {"ok":"bool"}, 1, lambda a: _get("/mem/prov/status"))
    register("mem.prov.enable", {"enable":"bool"}, {"ok":"bool"}, 1, lambda a: _post("/mem/prov/enable", {"enable": bool(a.get("enable",True))}))

    register("mem.entity.link", {"items":"list","upsert":"bool"}, {"ok":"bool"}, 2, lambda a: _post("/mem/entity/link", {"items": list(a.get("items") or []), "upsert": bool(a.get("upsert",True))}))
    register("mem.entity.status", {}, {"ok":"bool"}, 1, lambda a: _get("/mem/entity/status"))

    register("rag.hybrid.query", {"q":"str","top_k":"number"}, {"ok":"bool"}, 1, lambda a: _post("/rag/hybrid/query", {"q": a.get("q",""), "top_k": int(a.get("top_k",0) or 0)}))

    register("ingest.guard.status", {}, {"ok":"bool"}, 1, lambda a: _get("/ingest/guard/status"))
    register("ingest.guard.submit", {"source":"str","payload":"object"}, {"ok":"bool"}, 2, lambda a: _post("/ingest/guard/submit", {"source": a.get("source","default"), "payload": dict(a.get("payload") or {})}))

    register("security.rbac.status", {}, {"ok":"bool"}, 1, lambda a: _get("/security/rbac/status"))
    register("security.rbac.config", {"map":"object"}, {"ok":"bool"}, 1, lambda a: _post("/security/rbac/config", dict(a.get("map") or {})))
_reg()
# c=a+b