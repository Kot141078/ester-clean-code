# -*- coding: utf-8 -*-
"""routes/mem_kg_routes.py - pamyat (/memory + /mem) i graf znaniy (/mem/kg, /mem/hypothesis).
Drop-in: modul registriruetsya iz wsgi_secure.py i podnimaet svyazannye routy.

Vklyuchaet:
  /memory/flashback (GET)
  /memory/alias (POST)
  /memory/compact (POST)
  A takzhe aliasy na /mem/flashback, /mem/alias, /mem/compact

Graf znaniy:
  /mem/kg/upsert (POST)
  /mem/kg/query (GET)
  /mem/kg/export (GET)
  /mem/kg/import (POST)

Hypothesis/ideas:
  /mem/hypothesis (GET, POST) - integratsiya s idea.py (kak istochnikom idey) + khranenie.

Khranenie:
  - StructuredMemory - kak v ostalnykh modulyakh
  - KG: PERSIST_DIR/kg/graph.json (nodes[], edges[])
  - Alias map: PERSIST_DIR/structured_mem/alias.json
  - Hypothesis stash: PERSIST_DIR/hypothesis.jsonl"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from flask import jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# fallback alias map for read-only/locked state dirs
_ALIAS_MEM: Dict[str, str] = {}
_KG_SCOPE: str = ""

# -------- memory/manager --------


def _persist_dir() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(base, exist_ok=True)
    return base


def _build_mm():
    from cards_memory import CardsMemory  # type: ignore
    from memory_manager import MemoryManager  # type: ignore
    from structured_memory import StructuredMemory  # type: ignore
    from vector_store import VectorStore  # type: ignore

    persist_dir = _persist_dir()
    vstore = VectorStore(
        collection_name=os.getenv("COLLECTION_NAME", "ester_store"),
        persist_dir=persist_dir,
        use_embeddings=bool(int(os.getenv("USE_EMBEDDINGS", "0"))),
        embeddings_api_base=os.getenv("EMBEDDINGS_API_BASE", ""),
        embeddings_model=os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        embeddings_api_key=os.getenv("EMBEDDINGS_API_KEY", ""),
        use_local=bool(int(os.getenv("EMBEDDINGS_USE_LOCAL", "1"))),
    )
    structured = StructuredMemory(os.path.join(persist_dir, "structured_mem", "store.json"))  # type: ignore
    cards = CardsMemory(os.path.join(persist_dir, "ester_cards.json"))  # type: ignore
    return MemoryManager(vstore, structured, cards)  # type: ignore


def _clean_memory_path() -> str:
    return os.getenv("REST_CLEAN_MEMORY_PATH", os.path.join("data", "passport", "clean_memory.jsonl"))


def _flashback_from_clean_memory(query: str, k: int) -> List[Dict[str, Any]]:
    p = _clean_memory_path()
    if not os.path.exists(p):
        return []
    q = (query or "*").strip().lower()
    out: List[Dict[str, Any]] = []
    try:
        with open(p, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []

    for i, ln in enumerate(reversed(lines)):
        ln = (ln or "").strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        user = str(obj.get("user") or "").strip()
        assistant = str(obj.get("assistant") or "").strip()
        text = (assistant or user).strip()
        if not text:
            continue
        blob = f"{user}\n{assistant}".lower()
        if q != "*" and q not in blob:
            continue
        ts = float(obj.get("ts") or 0.0)
        score = 1.0 if (q == "*" or q in blob) else 0.0
        out.append(
            {
                "id": f"clean_{i}",
                "text": text,
                "tags": ["clean_memory"],
                "weight": 0.2,
                "score": score,
                "mtime": int(ts),
            }
        )
        if len(out) >= max(1, int(k or 50)):
            break
    return out


# -------- alias map --------


def _alias_path() -> str:
    p = os.path.join(_persist_dir(), "structured_mem", "alias.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _alias_load() -> Dict[str, str]:
    global _ALIAS_MEM
    base = dict(_ALIAS_MEM if isinstance(_ALIAS_MEM, dict) else {})
    p = _alias_path()
    if not os.path.exists(p):
        return base
    try:
        with open(p, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            base.update({str(k): str(v) for k, v in obj.items()})
        return base
    except Exception:
        return base


def _alias_save(j: Dict[str, str]) -> None:
    global _ALIAS_MEM
    _ALIAS_MEM = dict(j or {})
    p = _alias_path()
    tmp = p + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(j, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        # read-only/locked FS: keep aliases in-memory for current process
        return


# -------- structured store raw --------


def _structured_path() -> str:
    p = os.path.join(_persist_dir(), "structured_mem", "store.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _structured_load() -> List[Dict[str, Any]]:
    p = _structured_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
    except Exception:
        return []
    return []


def _structured_save(items: List[Dict[str, Any]]) -> None:
    p = _structured_path()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


# -------- KG storage (faylovoe) --------


def _kg_path() -> str:
    p = os.path.join(_persist_dir(), "kg", "graph.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _kg_load() -> Dict[str, Any]:
    p = _kg_path()
    if not os.path.exists(p):
        return {"nodes": [], "edges": []}
    try:
        with open(p, "r", encoding="utf-8") as f:
            j = json.load(f)
        if "nodes" not in j:
            j["nodes"] = []
        if "edges" not in j:
            j["edges"] = []
        return j
    except Exception:
        return {"nodes": [], "edges": []}


def _kg_save(j: Dict[str, Any]) -> None:
    p = _kg_path()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(j, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


# -------- idea integration (hypothesis) --------


def _hypo_path() -> str:
    p = os.path.join(_persist_dir(), "hypothesis.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _hypo_append(obj: Dict[str, Any]) -> None:
    p = _hypo_path()
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


# -------- routes --------


def _mm():
    """Lazy memory manager singleton."""
    global _MM
    try:
        return _MM
    except NameError:
        _MM = _build_mm()
        return _MM


def _kg():
    """Lenivyy singleton KGStore."""
    from memory.kg_store import KGStore  # lazy

    global _KG, _KG_SCOPE
    scope = _persist_dir()
    try:
        if _KG_SCOPE != scope:
            _KG = KGStore()
            _KG_SCOPE = scope
        return _KG
    except NameError:
        _KG = KGStore()
        _KG_SCOPE = scope
        return _KG


def _hs():
    """Lenivyy singleton HypothesisStore."""
    from memory.hypothesis_store import HypothesisStore  # lazy

    global _HS
    try:
        return _HS
    except NameError:
        _HS = HypothesisStore()
        return _HS


def _register_memory_routes(app, base: str = "/memory"):
    """Registers /<base>/ZZF0Z. For aliases we call twice."""
    # a unique prefix of endpoints so that they do not overlap when re-registering
    ep_prefix = (base or "/").strip("/").replace("/", "_") or "root"
    ep_ns = f"memkg_{ep_prefix}"

    @app.get(base + "/flashback", endpoint=f"{ep_ns}_flashback")
    @jwt_required()
    def memory_flashback():
        q = request.args.get("query", request.args.get("q", "*"))
        try:
            k = int(request.args.get("k", "50"))
        except Exception:
            k = 50
        if k <= 0:
            empty: List[Dict[str, Any]] = []
            return jsonify({"ok": True, "results": empty, "items": empty, "flashback": empty})

        out: List[Dict[str, Any]] = []
        try:
            out = _mm().flashback(query=q, k=max(1, int(k)))  # type: ignore[attr-defined]
        except Exception:
            out = []
        if not out:
            out = _flashback_from_clean_memory(query=q, k=max(1, int(k)))
        return jsonify({"ok": True, "results": out, "items": out, "flashback": out})

    @app.post(base + "/alias", endpoint=f"{ep_ns}_alias")
    @jwt_required()
    def memory_alias():
        """POST compatibility:
        {src,dst} | {old_doc_id,new_doc_id} | {doc_id,alias}.
        """
        data = request.get_json(silent=True) or {}
        src = str(data.get("src") or data.get("old_doc_id") or data.get("doc_id") or "").strip()
        dst = str(data.get("dst") or data.get("new_doc_id") or data.get("alias") or "").strip()
        if not src or not dst:
            return jsonify({"ok": False, "error": "src/dst required"}), 400
        ok = False
        try:
            rep = _mm().alias(src, dst)  # type: ignore[attr-defined]
            ok = bool((rep or {}).get("ok"))
        except Exception:
            ok = False
        if not ok:
            # fallback for non-structured ids (e.g. clean-memory results)
            alias = _alias_load()
            alias[src] = dst
            _alias_save(alias)
        return jsonify({"ok": True, "doc_id": src, "alias": dst, "old_doc_id": src, "new_doc_id": dst})

    @app.post(base + "/compact", endpoint=f"{ep_ns}_compact")
    @jwt_required()
    def memory_compact():
        data = request.get_json(silent=True) or {}
        dry = bool(data.get("dry_run", False) or data.get("dry", False))
        try:
            rep = dict(_mm().compact(dry_run=dry) or {})  # type: ignore[attr-defined]
        except Exception:
            rep = {"deleted": 0, "merged": 0, "dry_run": dry}
        rep.setdefault("deleted", 0)
        rep.setdefault("merged", 0)
        rep["ok"] = True
        rep["stats"] = {"deleted": rep.get("deleted", 0), "merged": rep.get("merged", 0)}
        return jsonify(rep)


def _register_kg_routes(app):
    @app.post("/mem/kg/upsert", endpoint="memkg_upsert")
    @jwt_required()
    def kg_upsert():
        """POST { nodes: [...], edges: [...] }"""
        data = request.get_json(silent=True) or {}
        nodes = [x for x in (data.get("nodes") or []) if isinstance(x, dict)]
        edges = [x for x in (data.get("edges") or []) if isinstance(x, dict)]
        nn = _kg().upsert_nodes(nodes)
        ee = _kg().upsert_edges(edges)
        return jsonify({"ok": True, "nodes": len(nn), "edges": len(ee)})

    @app.get("/mem/kg/query", endpoint="memkg_query")
    @jwt_required()
    def kg_query():
        """
        GET /mem/kg/query?q=replication&type=topic&limit=50
        GET /mem/kg/query?rel=supports&src=a&dst=b&limit=50
        """
        q = request.args.get("q")
        t = request.args.get("type")
        rel = request.args.get("rel")
        src = request.args.get("src")
        dst = request.args.get("dst")
        limit = int(request.args.get("limit", "100"))
        if rel or src or dst:
            edges = _kg().query_edges(rel=rel, src=src, dst=dst, limit=limit)
            return jsonify({"ok": True, "edges": edges})
        nodes = _kg().query_nodes(q=q or "", type=t, limit=limit)
        return jsonify({"ok": True, "nodes": nodes})

    @app.get("/mem/kg/export", endpoint="memkg_export")
    @jwt_required()
    def kg_export():
        payload = _kg().export_all()
        if isinstance(payload, dict):
            return jsonify({"ok": True, **payload})
        return jsonify({"ok": True, "nodes": [], "edges": []})

    @app.get("/mem/kg/neighbors", endpoint="memkg_neighbors")
    @jwt_required()
    def kg_neighbors():
        nid = str(request.args.get("id") or request.args.get("node_id") or "").strip()
        if not nid:
            return jsonify({"ok": False, "error": "id required"}), 400
        rel = request.args.get("rel")
        return jsonify(_kg().neighbors(node_id=nid, rel=rel))

    @app.post("/mem/kg/import", endpoint="memkg_import")
    @jwt_required()
    def kg_import():
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"ok": False, "error": "payload must be object"}), 400
        res = _kg().import_all(data)
        return jsonify({"ok": True, **res})


def _register_hypothesis_routes(app):
    @app.get("/mem/hypothesis", endpoint="memkg_hypothesis_list")
    @jwt_required()
    def hs_list():
        topic = request.args.get("topic")
        limit = int(request.args.get("limit", "100"))
        items = _hs().list(topic=topic, limit=limit)
        return jsonify({"ok": True, "items": items})

    @app.post("/mem/hypothesis", endpoint="memkg_hypothesis_add")
    @jwt_required()
    def hs_add():
        data = request.get_json(silent=True) or {}
        text = str(data.get("text") or "").strip()
        topic = str(data.get("topic") or "").strip()
        tags = data.get("tags") or []
        score = float(data.get("score") or 0.5)
        if not text:
            return jsonify({"ok": False, "error": "text required"}), 400
        _hs().add(text=text, topic=topic, tags=tags, score=score)
        # metka v pamyat — best-effort
        try:
            _mm().structured.add_record(text=f"[HYP] {text}", tags=["hypothesis"] + list(tags))  # type: ignore[attr-defined]
        except Exception:
            pass
        return jsonify({"ok": True, "saved": True})


def register_mem_kg_routes(app, url_prefix: str = "/memory"):  # URL_prefix is ​​saved for compatibility signature
    """Main entry point: registers:
      /memory/* and aliases /topics/*
      /tem/kg/*, /tem/hopotnesis"""
    # Idempotency: if the key CG route already exists, we do not register it again.
    if any(r.rule == "/mem/kg/upsert" for r in app.url_map.iter_rules()):
        return
    # Memory pod /memory/*
    _register_memory_routes(app, "/memory")
    # Aliasy pod /mem/*
    _register_memory_routes(app, "/mem")
    # KG i hypothesis
    _register_kg_routes(app)
    _register_hypothesis_routes(app)


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
def register(app):
    # Calls an existing register_topics_kg_rutes(app) (url_prefix is ​​taken by default inside the function)
    return register_mem_kg_routes(app)
# === /AUTOSHIM ===
