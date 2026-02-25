# -*- coding: utf-8 -*-
"""modules/thinking/actions_passport_kg_rag_ingest.py - eksheny "voli" dlya Profile/KG/RAG/Ingest/RBAC.

Mosty:
- Yavnyy: (Mysli ↔ Infrastruktura) fiksirovat profile, linkovat suschnosti, iskat, dozirovat ingest.
- Skrytyy #1: (Plan ↔ Ostorozhnost) proverka kvot pered zagruzkoy istochnikov.
- Skrytyy #2: (Prozrachnost ↔ Samoopis) roli i sostoyanie dostupny v myslyakh.

Zemnoy abzats:
Gorst korotkikh komand - i Ester mozhet akkuratno “smotret mir”, pomnit ego istochniki, nakhodit nuzhnoe i ne dushit set.

# c=a+b"""
from __future__ import annotations
import json, urllib.request
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def _get(path: str, timeout: int=15):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    def _post(path: str, payload: Dict[str,Any], timeout: int=60):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    # Profile
    register("mem.passport.append", {"note":"str","meta":"object","source":"str"}, {"ok":"bool"}, 1,
             lambda a: _post("/mem/passport/append", {"note": a.get("note",""), "meta": dict(a.get("meta") or {}), "source": a.get("source","")}))
    register("mem.passport.list", {"limit":"number"}, {"ok":"bool"}, 1,
             lambda a: _get(f"/mem/passport/list?limit={int(a.get('limit',50))}"))

    # KG avtolink
    register("mem.kg.autolink", {"items":"list","tags":"list"}, {"ok":"bool"}, 2,
             lambda a: _post("/mem/kg/autolink", {"items": list(a.get("items") or []), "tags": list(a.get("tags") or [])}))
    register("mem.kg.stats", {}, {"ok":"bool"}, 1,
             lambda a: _get("/mem/kg/stats"))

    # RAG gibrid
    register("rag.hybrid.search", {"query":"str","top_k":"number"}, {"ok":"bool"}, 1,
             lambda a: _post("/rag/hybrid/search", {"query": a.get("query",""), "top_k": int(a.get("top_k",10))}))

    # Ingest guard
    register("ingest.guard.check", {"source":"str","cost":"number"}, {"ok":"bool"}, 1,
             lambda a: _post("/ingest/guard/check", {"source": a.get("source","default"), "cost": int(a.get("cost",1))}))
    register("ingest.guard.state", {}, {"ok":"bool"}, 1,
             lambda a: _get("/ingest/guard/state"))
    register("ingest.guard.config", {"source":"str","rate_per_min":"number","burst":"number"}, {"ok":"bool"}, 1,
             lambda a: _post("/ingest/guard/config", {"source": a.get("source","default"), "rate_per_min": int(a.get("rate_per_min",60)), "burst": int(a.get("burst",120))}))

    # RBAC
    register("auth.roles.me", {}, {"ok":"bool"}, 1, lambda a: _get("/auth/roles/me"))

_reg()
# c=a+b