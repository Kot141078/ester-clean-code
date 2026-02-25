# -*- coding: utf-8 -*-
"""modules/thinking/actions_mem_rag.py - eksheny “voli” dlya profilea, linkera i gibridnogo poiska.

Mosty:
- Yavnyy: (Mysli ↔ Memory/Poisk) korotkie komandy dlya zapisi profilea, razmetki suschnostey i RAG.
- Skrytyy #1: (RBAC/Politiki) idut cherez REST — uvazhaem obschie pravila.
- Skrytyy #2: (Planirovschik ↔ Avtonomiya) legko vklyuchit po taymeru/sobytiyu.

Zemnoy abzats:
Mozgu ne nuzhno pomnit URL - “zapishi profile”, “razmet suschnosti”, “naydi relevantnoe” i poekhali.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return
    import json, urllib.request

    def _post(path: str, payload: Dict[str,Any], timeout: int=30):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    def a_passport(args: Dict[str,Any]):
        return _post("/mem/passport/upsert", {"note": str(args.get("note","")), "meta": dict(args.get("meta") or {}), "source": str(args.get("source","think://volition"))})
    register("mem.passport.upsert", {"note":"str"}, {"ok":"bool"}, 1, a_passport)

    def a_link(args: Dict[str,Any]):
        return _post("/mem/entity/link", {"text": str(args.get("text","")), "attach_to": args.get("attach_to")})
    register("mem.entity.link", {"text":"str"}, {"ok":"bool"}, 2, a_link)

    def a_hybrid(args: Dict[str,Any]):
        return _post("/rag/hybrid/search", {"query": str(args.get("query","")), "top_k": int(args.get("top_k",5)), "corpus": list(args.get("corpus") or [])}, timeout=21600)
    register("rag.hybrid.search", {"query":"str"}, {"ok":"bool"}, 3, a_hybrid)

_reg()
# c=a+b



