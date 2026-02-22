# -*- coding: utf-8 -*-
"""
modules/thinking/actions_rag.py — eksheny dlya RAG i kvot ingest.

Mosty:
- Yavnyy: (Mysli ↔ Poisk/Kvoty) mozg mozhet sam vyzyvat gibridnyy poisk i proveryat baket.
- Skrytyy #1: (Avtonomiya ↔ Ostorozhnost) pered tyazhelymi zadachami proveryaem limity.
- Skrytyy #2: (RAG ↔ KG) mozhno podavat teksty, sformirovannye iz KG/pamyati.

Zemnoy abzats:
V stsenariyakh mysli teper est kirpichiki «poisk» i «proverka topliva».

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def a_rag(args: Dict[str,Any]):
        from modules.rag.hybrid import hybrid_query
        return {"ok": True, "hits": hybrid_query(str(args.get("q","")), list(args.get("texts") or []), int(args.get("k",5)))}
    register("rag.query", {"q":"str","texts":"list","k":"int"}, {"ok":"bool","hits":"list"}, 15, a_rag)

    def a_quota(args: Dict[str,Any]):
        from modules.ingest.backpressure import consume
        return consume(str(args.get("source","unknown")), float(args.get("cost",1.0)))
    register("ingest.quota.consume", {"source":"str","cost":"float"}, {"ok":"bool"}, 3, a_quota)

_reg()
# c=a+b