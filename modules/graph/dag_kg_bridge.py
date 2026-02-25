
# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.graph.dag_kg_bridge - most mezhdu DAG‑dvizhkom i KG‑uzlami.
Mosty:
- Yavnyy: build_graph_for_entity()/run_graph() — prostaya sborka DAG vokrug kg_nodes.*.
- Skrytyy #1: (DX ↔ Sovmestimost) — ne trogaem dag_engine; ispolzuem ego publichnyy build_graph().
- Skrytyy #2: (Memory ↔ Orkestratsiya) — deklarativnaya sborka plana (entity + relations).

Zemnoy abzats:
Eto "soedinitelnaya tkan" mezhdu planirovaniem (DAG) i znaniyami (KG): add suschnost i svyazi - zapustili graf.
# c=a+b"""
from typing import Dict, Any, List, Tuple, Optional
from importlib import import_module
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _kg():
    from modules.graph import kg_nodes as kg  # local import for sustainability
    return kg

def make_add_entity_node(eid: str, labels: Optional[List[str]]=None, props: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    def _fn(**k):
        return _kg().add_entity(eid, labels or [], props or {})
    return {"fn": _fn, "deps": []}

def make_add_relation_node(name: str, src: str, rel: str, dst: str, props: Optional[Dict[str,Any]]=None, deps: Optional[List[str]]=None) -> Tuple[str, Dict[str, Any]]:
    def _fn(**k):
        return _kg().add_relation(src, rel, dst, props or {})
    return name, {"fn": _fn, "deps": deps or []}

def build_graph_for_entity(eid: str, labels: Optional[List[str]]=None, props: Optional[Dict[str,Any]]=None,
                           relations: Optional[List[Tuple[str, str, str, Optional[Dict[str,Any]]]]]=None) -> Dict[str, Any]:
    """
    relations: spisok (src, rel, dst, props)
    """
    spec: Dict[str, Any] = {}
    spec["E"] = make_add_entity_node(eid, labels, props)
    # svyaz uzlov k E
    if relations:
        for i, (src, rel, dst, rprops) in enumerate(relations, start=1):
            name, node = make_add_relation_node(f"R{i}", src, rel, dst, rprops, deps=["E"])
            spec[name] = node
    return spec

def run_graph(spec: Dict[str, Any]) -> Dict[str, Any]:
    dg = import_module("modules.graph.dag_engine")
    g = dg.build_graph(spec)  # type: ignore
    return g.run()  # type: ignore