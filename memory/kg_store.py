# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _persist_dir() -> Path:
    return Path(os.getenv("PERSIST_DIR") or Path.cwd() / "data")


def _graph_path() -> Path:
    return _persist_dir() / "kg" / "graph.json"


def _now() -> float:
    return float(time.time())


def _edge_id(src: str, rel: str, dst: str) -> str:
    return f"{src}::{rel}::{dst}"


def _edge_key(edge: Dict[str, Any]) -> Tuple[str, str, str]:
    return (str(edge.get("src") or ""), str(edge.get("rel") or ""), str(edge.get("dst") or ""))


def _as_props(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_tags(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, dict)):
        return [str(x) for x in value]
    return []


class KGStore:
    """Small JSON-backed compatibility KG for legacy memory.kg_store imports."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path) if path else _graph_path()
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        for node in payload.get("nodes") or []:
            if isinstance(node, dict) and str(node.get("id") or ""):
                norm = self._normalize_node(node)
                self._nodes[str(norm["id"])] = norm
        for edge in payload.get("edges") or []:
            if isinstance(edge, dict):
                norm = self._normalize_edge(edge)
                key = _edge_key(norm)
                if all(key):
                    self._edges[key] = norm

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.export_all()
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def _normalize_node(self, node: Dict[str, Any]) -> Dict[str, Any]:
        node_id = str(node.get("id") or node.get("label") or "").strip()
        mtime = float(node.get("mtime") or _now())
        return {
            "id": node_id,
            "type": str(node.get("type") or "entity"),
            "label": str(node.get("label") or node_id),
            "props": _as_props(node.get("props")),
            "tags": _as_tags(node.get("tags")),
            "mtime": mtime,
        }

    def _normalize_edge(self, edge: Dict[str, Any]) -> Dict[str, Any]:
        src = str(edge.get("src") or edge.get("source") or "").strip()
        rel = str(edge.get("rel") or edge.get("type") or "related").strip()
        dst = str(edge.get("dst") or edge.get("target") or "").strip()
        mtime = float(edge.get("mtime") or _now())
        weight = float(edge.get("weight") if edge.get("weight") is not None else 1.0)
        edge_id = str(edge.get("id") or _edge_id(src, rel, dst))
        return {
            "id": edge_id,
            "src": src,
            "rel": rel,
            "dst": dst,
            "weight": weight,
            "props": _as_props(edge.get("props")),
            "tags": _as_tags(edge.get("tags")),
            "mtime": mtime,
        }

    def upsert_nodes(self, nodes: Iterable[Dict[str, Any]]) -> List[str]:
        out: List[str] = []
        changed = False
        for raw in nodes or []:
            if not isinstance(raw, dict):
                continue
            node = self._normalize_node(raw)
            node_id = str(node.get("id") or "")
            if not node_id:
                continue
            old = self._nodes.get(node_id)
            if old is None:
                self._nodes[node_id] = node
                changed = True
            elif float(node["mtime"]) >= float(old.get("mtime") or 0.0):
                merged_props = {**_as_props(old.get("props")), **_as_props(node.get("props"))}
                merged_tags = sorted(set(_as_tags(old.get("tags"))) | set(_as_tags(node.get("tags"))))
                self._nodes[node_id] = {
                    **old,
                    **node,
                    "props": merged_props,
                    "tags": merged_tags,
                }
                changed = True
            out.append(node_id)
        if changed:
            self._save()
        return out

    def upsert_edges(self, edges: Iterable[Dict[str, Any]]) -> List[str]:
        out: List[str] = []
        changed = False
        for raw in edges or []:
            if not isinstance(raw, dict):
                continue
            edge = self._normalize_edge(raw)
            key = _edge_key(edge)
            if not all(key):
                continue
            old = self._edges.get(key)
            if old is None:
                self._edges[key] = edge
                changed = True
            else:
                merged = dict(old)
                merged["weight"] = max(float(old.get("weight") or 0.0), float(edge.get("weight") or 0.0))
                if float(edge["mtime"]) >= float(old.get("mtime") or 0.0):
                    merged.update(
                        {
                            "id": str(edge.get("id") or old.get("id") or _edge_id(*key)),
                            "props": {**_as_props(old.get("props")), **_as_props(edge.get("props"))},
                            "tags": sorted(set(_as_tags(old.get("tags"))) | set(_as_tags(edge.get("tags")))),
                            "mtime": float(edge["mtime"]),
                        }
                    )
                self._edges[key] = merged
                changed = True
            out.append(str(self._edges[key].get("id") or _edge_id(*key)))
        if changed:
            self._save()
        return out

    def query_nodes(
        self,
        q: str = "",
        type: Optional[str] = None,
        limit: int = 50,
        **_: Any,
    ) -> List[Dict[str, Any]]:
        ql = str(q or "").lower().strip()
        type_filter = str(type).lower() if type else ""
        rows: List[Dict[str, Any]] = []
        for node in self._nodes.values():
            if type_filter and str(node.get("type") or "").lower() != type_filter:
                continue
            haystack = " ".join(
                [
                    str(node.get("id") or ""),
                    str(node.get("label") or ""),
                    json.dumps(node.get("props") or {}, ensure_ascii=False),
                ]
            ).lower()
            if ql and ql not in haystack:
                continue
            rows.append(dict(node))
        rows.sort(key=lambda item: float(item.get("mtime") or 0.0), reverse=True)
        return rows[: max(0, int(limit or 50))]

    def query_edges(
        self,
        rel: Optional[str] = None,
        src: Optional[str] = None,
        dst: Optional[str] = None,
        limit: int = 50,
        **_: Any,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for edge in self._edges.values():
            if rel is not None and str(edge.get("rel") or "") != str(rel):
                continue
            if src is not None and str(edge.get("src") or "") != str(src):
                continue
            if dst is not None and str(edge.get("dst") or "") != str(dst):
                continue
            rows.append(dict(edge))
        rows.sort(key=lambda item: float(item.get("mtime") or 0.0), reverse=True)
        return rows[: max(0, int(limit or 50))]

    def neighbors(self, node_id: str, rel: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        node = dict(self._nodes.get(str(node_id), {"id": str(node_id), "type": "entity", "label": str(node_id)}))
        out = self.query_edges(src=str(node_id), rel=rel, limit=limit)
        inc = self.query_edges(dst=str(node_id), rel=rel, limit=limit)
        return {"node": node, "out": out, "in": inc}

    def export_all(self) -> Dict[str, List[Dict[str, Any]]]:
        nodes = [dict(x) for x in self._nodes.values()]
        edges = [dict(x) for x in self._edges.values()]
        nodes.sort(key=lambda item: str(item.get("id") or ""))
        edges.sort(
            key=lambda item: (
                str(item.get("src") or ""),
                str(item.get("rel") or ""),
                str(item.get("dst") or ""),
            )
        )
        return {"nodes": nodes, "edges": edges}

    def import_all(self, payload: Dict[str, Any], policy: str = "merge") -> Dict[str, int]:
        return self.import_graph(payload, policy=policy)

    def import_graph(self, payload: Dict[str, Any], policy: str = "merge") -> Dict[str, int]:
        if str(policy or "merge").lower() == "replace":
            self._nodes = {}
            self._edges = {}
        node_ids = self.upsert_nodes(payload.get("nodes") or [])
        edge_ids = self.upsert_edges(payload.get("edges") or [])
        if not node_ids and not edge_ids and str(policy or "").lower() == "replace":
            self._save()
        return {"nodes": len(node_ids), "edges": len(edge_ids)}

    def repair(self) -> Dict[str, int]:
        self._save()
        return {"nodes": len(self._nodes), "edges": len(self._edges)}

    def add_record(self, record_id: str, payload: Dict[str, Any]) -> str:
        text = str((payload or {}).get("text") or record_id)
        self.upsert_nodes(
            [
                {
                    "id": f"record::{record_id}",
                    "type": "record",
                    "label": text[:120],
                    "props": dict(payload or {}),
                    "mtime": _now(),
                }
            ]
        )
        return str(record_id)

    def add_edge(self, payload: Dict[str, Any]) -> str:
        label = str((payload or {}).get("label") or "artifact")
        dst = f"artifact::{label}"
        self.upsert_nodes([{"id": dst, "type": "artifact", "label": label, "props": dict(payload or {})}])
        edge_id = self.upsert_edges([{"src": "ingest", "rel": "mentions", "dst": dst, "props": dict(payload or {})}])
        return edge_id[0] if edge_id else ""


_STORE: Optional[KGStore] = None
_STORE_SCOPE = ""


def _default_store() -> KGStore:
    global _STORE, _STORE_SCOPE
    scope = str(_graph_path())
    if _STORE is None or _STORE_SCOPE != scope:
        _STORE = KGStore()
        _STORE_SCOPE = scope
    return _STORE


def upsert_entity(
    eid: str,
    labels: Optional[List[str]] = None,
    props: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    node_type = labels[0] if labels else "entity"
    _default_store().upsert_nodes([{"id": eid, "type": node_type, "label": eid, "props": props or {}}])
    return {"ok": True, "id": eid}


def upsert_relation(src: str, rel: str, dst: str, props: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _default_store().upsert_edges([{"src": src, "rel": rel, "dst": dst, "props": props or {}}])
    return {"ok": True, "src": src, "rel": rel, "dst": dst}


def query(label: Optional[str] = None, where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rows = _default_store().query_nodes(type=label or None, limit=1000)
    where = where or {}
    if where:
        rows = [row for row in rows if all((row.get("props") or {}).get(k) == v for k, v in where.items())]
    return {"ok": True, "items": rows}


def export_snapshot() -> Dict[str, Any]:
    data = _default_store().export_all()
    return {"entities": data["nodes"], "edges": data["edges"]}


snapshot = export_snapshot
dump = export_snapshot
export = export_snapshot


def list_entities() -> List[Dict[str, Any]]:
    return export_snapshot()["entities"]


def list_relations() -> List[Dict[str, Any]]:
    return export_snapshot()["edges"]


__all__ = [
    "KGStore",
    "upsert_entity",
    "upsert_relation",
    "query",
    "export_snapshot",
    "snapshot",
    "dump",
    "export",
    "list_entities",
    "list_relations",
]
