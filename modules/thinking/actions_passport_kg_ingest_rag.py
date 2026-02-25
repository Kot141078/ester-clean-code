# -*- coding: utf-8 -*-
"""modules/thinking/actions_passport_kg_ingest_rag.py - eksheny "voli" dlya Passport/KG/IngestGuard/RAG.

Mosty:
- Yavnyy: (Mysli ↔ Memory/Graf/Kvoty/Poisk) korotkie komandy dlya vnutrennikh payplaynov.
- Skrytyy #1: (Profile ↔ Prozrachnost) lyubye vyzovy ostavlyayut sled.
- Skrytyy #2: (Cron/Avtonomiya ↔ Plan) mozhno triggerit eti shagi po raspisaniyu/sobytiyam.

Zemnoy abzats:
Nabor “mgnovennykh knopok”: proshtampovat, svyazat suschnosti, ask kvotu, nayti po gibridu.

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

    register("mem.passport.append", {"note":"str","meta":"object","source":"str","version":"str"}, {"ok":"bool"}, 1,
             lambda a: _post("/mem/passport/append", {"note": a.get("note",""), "meta": dict(a.get("meta") or {}), "source": a.get("source","thinking://"), "version": a.get("version","1")}))

    register("mem.kg.autolink", {"items":"list"}, {"ok":"bool"}, 2,
             lambda a: _post("/mem/kg/autolink", {"items": list(a.get("items") or [])}))

    register("ingest.guard.check", {"source":"str","cost":"number"}, {"ok":"bool"}, 1,
             lambda a: _post("/ingest/guard/check", {"source": a.get("source","default"), "cost": int(a.get("cost",0))}))

    register("rag.hybrid.search", {"q":"str","top_k":"number"}, {"ok":"bool"}, 1,
             lambda a: _post("/rag/hybrid/search", {"q": a.get("q",""), "top_k": int(a.get("top_k",0))}))
_reg()
# c=a+b