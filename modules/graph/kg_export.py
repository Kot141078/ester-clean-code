
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.graph.kg_export — eksport snapshota KG.
Mosty:
- Yavnyy: snapshot() vozvraschaet {"entities": [...], "edges": [...] } iz memory.kg_store ili iz in-proc folbeka kg_nodes.
- Skrytyy #1: (DX ↔ Sovmestimost) — probuem neskolko API: export_snapshot/dump/list_entities;list_relations.
- Skrytyy #2: (Inzheneriya ↔ Prozrachnost) — pomechaem istochnik dannykh v otvete (source).

Zemnoy abzats:
Snapshot — eto «srez tkaney»: bystro uvidet sostav i svyazi, ne vskryvaya ves organizm.
# c=a+b
"""
from typing import Dict, Any, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _from_kg_store() -> Optional[Dict[str, Any]]:
    try:
        from memory import kg_store as store  # type: ignore
    except Exception:
        return None
    # Pytaemsya raznye formy API
    for name in ("export_snapshot", "snapshot", "dump", "export"):
        fn = getattr(store, name, None)
        if callable(fn):
            try:
                snap = fn()  # type: ignore
                if isinstance(snap, dict) and "entities" in snap:
                    return {"ok": True, "entities": snap.get("entities", []), "edges": snap.get("edges", []), "source": "memory.kg_store."+name}
            except Exception:
                pass
    # list_entities/list_relations
    ents = getattr(store, "list_entities", None)
    rels = getattr(store, "list_relations", None)
    if callable(ents):
        try:
            e = ents()  # type: ignore
            r = rels() if callable(rels) else []  # type: ignore
            if isinstance(e, list):
                return {"ok": True, "entities": e, "edges": r if isinstance(r, list) else [], "source": "memory.kg_store.list_*"}
        except Exception:
            pass
    return None

def _from_fallback() -> Dict[str, Any]:
    try:
        from modules.graph import kg_nodes as kg
    except Exception:
        return {"ok": True, "entities": [], "edges": [], "source": "kg_nodes:missing"}
    # suschnosti: cherez query(None)
    try:
        ents = kg.query(None).get("items", [])  # type: ignore
    except Exception:
        ents = []
    # rebra: esli est skrytoe pole _FALLBACK
    try:
        edges = getattr(kg, "_FALLBACK", {}).get("edges", [])  # type: ignore
        if not isinstance(edges, list):
            edges = []
    except Exception:
        edges = []
    return {"ok": True, "entities": ents, "edges": edges, "source": "kg_nodes.fallback"}

def snapshot() -> Dict[str, Any]:
    snap = _from_kg_store()
    if snap is not None:
        return snap
    return _from_fallback()