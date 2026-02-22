# -*- coding: utf-8 -*-
"""
modules/graph — legkiy graf znaniy poverkh pamyati/suschnostey.

MOSTY:
- (Yavnyy) build_graph() -> {"nodes":[...], "edges":[...]}; summary(graph) -> kompaktnye metriki.
- (Skrytyy #1) Chitaet entities iz data/mem/entities i edge-dokumenty iz pamyati (semantic).
- (Skrytyy #2) Ne trebuet vneshnikh BD/bibliotek (closed_box), sokhranyaet format JSON.

ZEMNOY ABZATs:
«Naskalnaya karta» svyazey: kto s chem svyazan i skolko uzlov/reber — chtoby dalshe uzhe stroit analitiku.

# c=a+b
"""
from __future__ import annotations
import os, json, glob
from typing import Dict, Any, List, Set
from modules.memory.layers import _layer_dir  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ENT_DIR = os.path.join("data","mem","entities")

def _iter_entities():
    if not os.path.isdir(ENT_DIR):
        return
    for t in os.listdir(ENT_DIR):
        d = os.path.join(ENT_DIR, t)
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.endswith(".json"): continue
            try:
                with open(os.path.join(d, fn), "r", encoding="utf-8") as f:
                    yield json.load(f)
            except Exception:
                continue

def _iter_edges_from_memory():
    # «edge:entity:<id>::rel::doc:<id>» — my tak pishem ikh v memory_linker_routes
    for fp in glob.glob(os.path.join(_layer_dir("semantic"), "*.json")):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                doc = json.load(f)
            if isinstance(doc.get("text",""), str) and doc["text"].startswith("edge:"):
                yield doc
        except Exception:
            continue

def build_graph() -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    # nodes: entities
    for e in _iter_entities():
        nid = f"entity:{e.get('type','doc')}:{e.get('id')}"
        nodes[nid] = {"id": nid, "label": e.get("name") or nid, "type": e.get("type","doc")}

    # edges + doc nodes
    for ed in _iter_edges_from_memory():
        a = ed.get("meta",{}).get("a") or ""
        b = ed.get("meta",{}).get("b") or ""
        rel = ed.get("meta",{}).get("rel") or "rel"
        if a and b:
            if a not in nodes:
                nodes[a] = {"id": a, "label": a, "type": "virtual"}
            if b not in nodes:
                nodes[b] = {"id": b, "label": b, "type": "doc"}
            edges.append({"a": a, "b": b, "rel": rel})

    return {"nodes": list(nodes.values()), "edges": edges}

def summary(g: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "nodes": len(g.get("nodes",[])),
        "edges": len(g.get("edges",[])),
        "entity_nodes": sum(1 for n in g.get("nodes",[]) if str(n.get("id","")).startswith("entity:")),
        "doc_nodes": sum(1 for n in g.get("nodes",[]) if str(n.get("id","")).startswith("doc:")),
        "rels": sorted(list(set(e.get("rel","") for e in g.get("edges",[])))),
    }
# c=a+b