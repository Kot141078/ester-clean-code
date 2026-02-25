# -*- coding: utf-8 -*-
"""modules/thinking/actions_core15b.py - eksheny “voli” dlya gibridnogo poiska, ingest-proksi i P2P-filtra.

Mosty:
- Yavnyy: (Mysli ↔ Poisk/Ingest/P2P) korotkie komandy upravlyayut novymi vozmozhnostyami.
- Skrytyy #1: (Strategiya ↔ Ekonomika) ingest uvazhaet kvoty; search - quality.
- Skrytyy #2: (Set ↔ Konsolidatsiya) obmen Bloom-bitami snizhaet dubli.

Zemnoy abzats:
“Naydi luchshee”, “zagruzi akkuratno”, “ne taschi dublikaty” - tri rychaga na paneli voli.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def a_hybrid(args: Dict[str,Any]):
        from modules.search.hybrid import hybrid_query
        return hybrid_query(str(args.get("q","")), int(args.get("k",10)))
    register("search.hybrid.query", {"q":"str","k":"int"}, {"ok":"bool"}, 6, a_hybrid)

    def a_ingest_proxy(args: Dict[str,Any]):
        # we proxy through local HTTP so as not to tug on the internals directly
        import json, urllib.request
        body=json.dumps({"source": str(args.get("source","unknown")), "payload": dict(args.get("payload") or {}), "weight": float(args.get("weight",1.0))}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000/ingest/submit_proxy", data=body, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    register("ingest.submit.proxy", {"source":"str","payload":"dict"}, {"ok":"bool"}, 8, a_ingest_proxy)

    def a_p2p_merge(args: Dict[str,Any]):
        import json, urllib.request
        body=json.dumps({"bits": str(args.get("bits",""))}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000/p2p/filter/merge", data=body, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    register("p2p.filter.merge", {"bits":"str"}, {"ok":"bool"}, 2, a_p2p_merge)

_reg()
# c=a+b