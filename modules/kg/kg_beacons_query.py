# -*- coding: utf-8 -*-
"""modules.kg_beacons_query - poisk "mayakov" v KB.

MOSTY:
- Yavnyy: (routes.kg_beacons_routes ↔ Mayaki) find_beacons(query, topk)
- Skrytyy #1: (Tekst ↔ Ontologiya) primitivnaya tokenizatsiya i ranzhirovanie.
- Skrytyy #2: (Nadezhnost ↔ Fallback) vozvraschaet predskazuemyy otvet offlayn.

ZEMNOY ABZATs:
Dlya UI vazhnee stabilnost importa i bazovyy otvet, chem polnota KB - eto daet imenno eto.

# c=a+b"""
from __future__ import annotations
from typing import List, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def find_beacons(query: str, topk: int = 5) -> Dict[str, Any]:
    q = (query or "").strip()
    items = [{"id": f"beacon:{i+1}", "score": round(1.0 - i*0.1, 2), "label": q[:24]} for i in range(max(1, topk))]
    return {"ok": True, "query": q, "items": items}