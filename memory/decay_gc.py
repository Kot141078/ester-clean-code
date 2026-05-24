# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from memory.kg_store import KGStore


@dataclass
class DecayRules:
    half_life_s: float = 7 * 24 * 3600
    min_weight: float = 0.05
    gc_edge_min_age_s: float = 2 * 24 * 3600
    gc_edge_weight_threshold: float = 0.08
    gc_node_min_age_s: float = 3 * 24 * 3600


def _tags(value: Any) -> Set[str]:
    if isinstance(value, str):
        return {value.lower()}
    if isinstance(value, Iterable) and not isinstance(value, (bytes, dict)):
        return {str(x).lower() for x in value}
    return set()


def _is_pinned(item: Dict[str, Any]) -> bool:
    item_id = str(item.get("id") or "")
    if item_id.startswith("pin::"):
        return True
    props = item.get("props") if isinstance(item.get("props"), dict) else {}
    if props.get("pin") or props.get("pinned") or props.get("no_gc"):
        return True
    return bool(_tags(item.get("tags")) & {"pin", "pinned", "no_gc", "keep"})


class DecayGC:
    """Compatibility decay/GC pass for memory.kg_store graphs."""

    def __init__(self, kg: Optional[KGStore] = None) -> None:
        self.kg = kg or KGStore()

    def apply(self, rules: Optional[DecayRules] = None) -> Dict[str, Any]:
        rules = rules or DecayRules()
        now = float(time.time())
        graph = self.kg.export_all()
        nodes: List[Dict[str, Any]] = [dict(x) for x in graph.get("nodes", [])]
        edges: List[Dict[str, Any]] = [dict(x) for x in graph.get("edges", [])]
        node_by_id = {str(node.get("id") or ""): node for node in nodes}

        kept_edges: List[Dict[str, Any]] = []
        removed_edges: List[Dict[str, Any]] = []
        decayed_edges = 0

        for edge in edges:
            src = str(edge.get("src") or "")
            dst = str(edge.get("dst") or "")
            pinned = _is_pinned(edge) or _is_pinned(node_by_id.get(src, {})) or _is_pinned(node_by_id.get(dst, {}))
            age = max(0.0, now - float(edge.get("mtime") or now))
            weight = float(edge.get("weight") if edge.get("weight") is not None else 1.0)

            if not pinned:
                if rules.half_life_s > 0:
                    weight = weight * math.pow(0.5, age / float(rules.half_life_s))
                    decayed_edges += 1
                if age >= float(rules.gc_edge_min_age_s) and weight < float(rules.gc_edge_weight_threshold):
                    removed_edges.append(edge)
                    continue
                edge["weight"] = max(float(rules.min_weight), weight)

            kept_edges.append(edge)

        incident: Set[str] = set()
        for edge in kept_edges:
            incident.add(str(edge.get("src") or ""))
            incident.add(str(edge.get("dst") or ""))

        kept_nodes: List[Dict[str, Any]] = []
        removed_nodes: List[Dict[str, Any]] = []
        for node in nodes:
            node_id = str(node.get("id") or "")
            age = max(0.0, now - float(node.get("mtime") or now))
            if node_id and not _is_pinned(node) and node_id not in incident and age >= float(rules.gc_node_min_age_s):
                removed_nodes.append(node)
                continue
            kept_nodes.append(node)

        self.kg.import_graph({"nodes": kept_nodes, "edges": kept_edges}, policy="replace")
        return {
            "ok": True,
            "nodes": len(kept_nodes),
            "edges": len(kept_edges),
            "decayed_edges": decayed_edges,
            "removed_nodes": len(removed_nodes),
            "removed_edges": len(removed_edges),
        }


__all__ = ["DecayGC", "DecayRules"]
