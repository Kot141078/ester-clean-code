# -*- coding: utf-8 -*-
"""
routes/ops_routes.py - REST dlya operatsionnykh zadach: pokupki, zadaniya i GDPR.

Etot modul obedinyaet dva aspekta operatsionnoy deyatelnosti:
1.  **Spisok del i pokupok**: Planirovanie pokupok, naznachenie zadach i otslezhivanie ikh vypolneniya.
2.  **Instrumenty GDPR**: Upravlenie personalnymi dannymi, vklyuchaya eksport i bezopasnoe udalenie po zaprosu.

Endpointy:
  (Zadachi i pokupki)
  • POST /ops/shopping/plan      {"items":[{"name","qty"?,"budget"?,"tags"?[]}],"assign_to"?:"papa"}
  • GET  /ops/assignments
  • POST /ops/assignments/complete {"id": "<task_id>"}

  (GDPR)
  • POST /ops/export_personal_data   {"query":"stroka","download":false}
  • POST /ops/delete_personal_data   {"query":"stroka","dry_run":true}
"""
from __future__ import annotations

import io
import json
import os
from typing import Any, Dict, List, Tuple

from flask import Blueprint, Flask, Response, jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore

from memory.hypothesis_store import HypothesisStore
from memory.kg_store import KGStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# ---------- Initsializatsiya Blueprint ----------

bp_ops = Blueprint("ops", __name__)

# ---------- Integratsiya s modulem ops/shopping_list ----------

try:
    from modules.ops.shopping_list import add_assignments, complete_assignment, list_assignments  # type: ignore
except Exception:
    add_assignments = list_assignments = complete_assignment = None  # type: ignore

# ---------- GDPR: puti i utility ----------

def _persist_dir() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(base, exist_ok=True)
    return base

def _structured_path() -> str:
    p = os.path.join(_persist_dir(), "structured_mem", "store.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p

def _events_path() -> str:
    p = os.path.join(_persist_dir(), "events", "events.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if not os.path.exists(p):
        open(p, "w", encoding="utf-8").close()
    return p

def _to_str(v: Any) -> str:
    try:
        if isinstance(v, (dict, list, tuple)):
            return json.dumps(v, ensure_ascii=False)
        return str(v)
    except Exception:
        return str(v)

def _contains(obj: Any, ql: str) -> bool:
    if obj is None:
        return False
    if isinstance(obj, (str, bytes)):
        s = obj.decode("utf-8", "ignore") if isinstance(obj, bytes) else obj
        return ql in s.lower()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if ql in str(k).lower() or _contains(v, ql):
                return True
        return False
    if isinstance(obj, (list, tuple, set)):
        return any(_contains(x, ql) for x in obj)
    return ql in _to_str(obj).lower()

def _load_structured() -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
    """
    Vozvraschaet (records, raw_json_obj, format), gde format ∈ {"list","dict"}
    """
    p = _structured_path()
    if not os.path.exists(p):
        return [], {"records": [], "alias_map": {}}, "dict"
    try:
        raw = json.load(open(p, "r", encoding="utf-8"))
    except Exception:
        return [], {"records": [], "alias_map": {}}, "dict"
    if isinstance(raw, list):
        recs = [x for x in raw if isinstance(x, dict)]
        return recs, raw, "list"
    elif isinstance(raw, dict):
        recs = [x for x in (raw.get("records") or []) if isinstance(x, dict)]
        return recs, raw, "dict"
    else:
        return [], {"records": [], "alias_map": {}}, "dict"

def _save_structured(recs: List[Dict[str, Any]], raw: Any, fmt: str) -> None:
    p = _structured_path()
    tmp = p + ".tmp"
    if fmt == "list":
        data = recs
    else:
        obj = dict(raw or {})
        obj["records"] = recs
        data = obj
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)

# ---------- GDPR: yadro realizatsii ----------

def _export_personal_data_impl(query: str) -> Dict[str, Any]:
    ql = (query or "").strip().lower()
    # Structured
    s_recs, _, _ = _load_structured()
    s_hits = [r for r in s_recs if _contains(r, ql)] if ql else list(s_recs)

    # KG
    kg = KGStore()
    kg_dump = kg.export_all()
    n_hits = [
        n
        for n in kg_dump.get("nodes", [])
        if not ql or _contains(n.get("label") or "", ql) or _contains(n.get("props") or {}, ql)
    ]
    node_ids = {n["id"] for n in n_hits}
    e_hits = [
        e
        for e in kg_dump.get("edges", [])
        if (not ql or _contains(e.get("props") or {}, ql))
        or (e.get("src") in node_ids or e.get("dst") in node_ids)
    ]

    # Hypotheses
    hs = HypothesisStore()
    h_items = hs.list(limit=100000)
    h_hits = [
        h
        for h in h_items
        if (not ql) or _contains(h.get("text") or "", ql) or _contains(h.get("topic") or "", ql)
    ]

    # Events
    ev_path = _events_path()
    ev_hits: List[Dict[str, Any]] = []
    try:
        with open(ev_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    evt = json.loads(line)
                    if (not ql) or _contains(evt, ql):
                        ev_hits.append(evt)
                except Exception:
                    continue
    except Exception:
        pass

    return {
        "ok": True,
        "query": query,
        "counts": {
            "structured": len(s_hits),
            "kg_nodes": len(n_hits),
            "kg_edges": len(e_hits),
            "hypotheses": len(h_hits),
            "events": len(ev_hits),
        },
        "data": {
            "structured": s_hits,
            "kg": {"nodes": n_hits, "edges": e_hits},
            "hypotheses": h_hits,
            "events": ev_hits,
        },
    }

def _delete_personal_data_impl(query: str, dry_run: bool = True) -> Dict[str, Any]:
    ql = (query or "").strip().lower()
    report = {"ok": True, "dry_run": bool(dry_run), "query": query, "removed": {}}

    # Structured
    s_recs, s_raw, s_fmt = _load_structured()
    keep_recs = [r for r in s_recs if not _contains(r, ql)]
    rem_s = len(s_recs) - len(keep_recs)
    if not dry_run and rem_s > 0:
        _save_structured(keep_recs, s_raw, s_fmt)
    report["removed"]["structured"] = rem_s

    # KG
    kg = KGStore()
    dump = kg.export_all()
    nodes, edges = dump.get("nodes", []), dump.get("edges", [])
    del_nodes = {
        n["id"]
        for n in nodes
        if _contains(n.get("label") or "", ql) or _contains(n.get("props") or {}, ql)
    }
    keep_nodes = [n for n in nodes if n["id"] not in del_nodes]
    keep_nodes_ids = {n["id"] for n in keep_nodes}
    keep_edges = [
        e
        for e in edges
        if (e.get("src") in keep_nodes_ids and e.get("dst") in keep_nodes_ids)
        and not _contains(e.get("props") or {}, ql)
    ]
    rem_n, rem_e = len(nodes) - len(keep_nodes), len(edges) - len(keep_edges)
    if not dry_run and (rem_n > 0 or rem_e > 0):
        kg.import_graph({"nodes": keep_nodes, "edges": keep_edges}, policy="replace")
    report["removed"]["kg_nodes"] = rem_n
    report["removed"]["kg_edges"] = rem_e

    # Hypotheses
    hs = HypothesisStore()
    items = hs.list(limit=100000)
    keep_h = [
        h
        for h in items
        if not (_contains(h.get("text") or "", ql) or _contains(h.get("topic") or "", ql))
    ]
    rem_h = len(items) - len(keep_h)
    if not dry_run and rem_h > 0:
        path = hs.path
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(keep_h, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    report["removed"]["hypotheses"] = rem_h

    # Events JSONL
    try:
        ev_path = _events_path()
        with open(ev_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        keep_lines, rem_ev = [], 0
        for line in lines:
            try:
                if _contains(json.loads(line), ql):
                    rem_ev += 1
                else:
                    keep_lines.append(line)
            except Exception:
                rem_ev += 1  # Udalyaem povrezhdennye stroki
        if not dry_run and rem_ev > 0:
            tmp = ev_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(keep_lines)
            os.replace(tmp, ev_path)
        report["removed"]["events"] = rem_ev
    except Exception:
        report["removed"]["events"] = 0

    return report

# ---------- Marshruty (Routes) ----------

@bp_ops.route("/shopping/plan", methods=["POST"])
def api_shop_plan():
    """Sozdat spisok pokupok i naznachit ispolnitelya."""
    if add_assignments is None:
        return jsonify({"ok": False, "error": "ops module unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    items: List[Dict[str, Any]] = d.get("items") or []
    assign_to = str(d.get("assign_to", "papa"))
    return jsonify(add_assignments(items, assign_to=assign_to))

@bp_ops.route("/assignments", methods=["GET"])
def api_assignments():
    """Poluchit spisok vsekh aktivnykh zadaniy."""
    if list_assignments is None:
        return jsonify({"ok": False, "error": "ops module unavailable"}), 500
    return jsonify(list_assignments())

@bp_ops.route("/assignments/complete", methods=["POST"])
def api_assign_complete():
    """Otmetit zadanie kak vypolnennoe."""
    if complete_assignment is None:
        return jsonify({"ok": False, "error": "ops module unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(complete_assignment(str(d.get("id", ""))))

@bp_ops.route("/export_personal_data", methods=["POST"])
@jwt_required()
def export_personal_data():
    """Eksportirovat personalnye dannye po poiskovomu zaprosu."""
    data = request.get_json(silent=True) or {}
    q = str(data.get("query") or "").strip()
    download = bool(data.get("download") or False)
    out = _export_personal_data_impl(q)

    if download:
        buf = io.BytesIO(json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8"))
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Disposition": 'attachment; filename="personal_data_export.json"',
        }
        return Response(buf.getvalue(), headers=headers)
    return jsonify(out)

@bp_ops.route("/delete_personal_data", methods=["POST"])
@jwt_required()
def delete_personal_data():
    """Udalit personalnye dannye po poiskovomu zaprosu."""
    data = request.get_json(silent=True) or {}
    q = str(data.get("query") or "").strip()
    if not q:
        return jsonify({"ok": False, "error": "query is required"}), 400
    dry = bool(data.get("dry_run", True))
    out = _delete_personal_data_impl(q, dry_run=dry)
    return jsonify(out)

# ---------- Registratsiya Blueprint v prilozhenii ----------

def register(app: Flask):  # pragma: no cover
    """Registriruet ops blueprint v prilozhenii Flask."""
    app.register_blueprint(bp_ops, url_prefix="/ops")

def init_app(app: Flask):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)

__all__ = ["bp_ops", "register", "init_app"]
# c=a+b


def register(app):
    app.register_blueprint(bp_ops)
    return app
