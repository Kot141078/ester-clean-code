# -*- coding: utf-8 -*-
from __future__ import annotations
"""
/rag/status i /rag/hybrid/search

MOSTY:
- Yavnyy: Rout ↔ Retriver — korrektno prokidyvaem query/top_k i optsionalnye include_text/max_chars.
- Skrytyy #1: Prinimaem q|query|text|prompt|input i k|top_k|limit|n_results|n (gibkiy klient).
- Skrytyy #2: Chistim payload ot uzhe normalizovannykh klyuchey, chtoby ne dublirovat kwargs.

ZEMNOY ABZATs:
Python vydaet oshibku "got multiple values for keyword argument", esli odin i tot zhe parametr
peredan i imenovannym argumentom, i vnutri **kwargs. Lechim: vyrezaem normalizovannye klyuchi
iz payload pered vyzovom retrivera.
# c=a+b
"""
from typing import Any, Dict, Optional
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

rag_bp = Blueprint("rag_hybrid", __name__, url_prefix="/rag")

def _import_hybrid():
    try:
        from modules.rag.hybrid import search as hybrid_search  # type: ignore
        return hybrid_search, None
    except Exception as e:
        return None, e

# --- normalizatsiya vkhoda ---
def _norm_query(payload: Dict[str, Any]) -> str:
    for k in ("query", "q", "text", "prompt", "input"):
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""

def _norm_top_k(payload: Dict[str, Any], default: int = 6) -> int:
    for k in ("top_k", "k", "limit", "n_results", "n"):
        if k in payload:
            try:
                return int(payload.get(k))
            except Exception:
                pass
    return int(default)

def _coerce_bool(x: Any) -> Optional[bool]:
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return bool(x)
    if isinstance(x, str):
        return x.strip().lower() in ("1", "true", "yes", "on")
    return None

def _coerce_int(x: Any, default: Optional[int] = None) -> Optional[int]:
    if x is None:
        return default
    try:
        return int(x)
    except Exception:
        return default

def _clean_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ubiraem klyuchi, kotorye my uzhe normalizovali/prokinem yavno, chtoby ne zadublirovat."""
    block = {
        "query","q","text","prompt","input",
        "top_k","k","limit","n_results","n",
        "include_text","max_chars",
    }
    return {k: v for k, v in payload.items() if k not in block}

# --- endpointy ---
@rag_bp.get("/status")
def api_status():
    hybrid_search, err = _import_hybrid()
    notes = []
    if hybrid_search is None:
        notes.append("modules.rag.hybrid.search not available")
        return jsonify({"ok": False, "hybrid_available": False, "notes": notes}), 200

    try:
        res = hybrid_search(query="", top_k=0)
        return jsonify({
            "ok": True,
            "hybrid_available": True,
            "backend": res.get("backend"),
            "docs_path": res.get("docs_path"),
            "count_indexed": res.get("count_indexed"),
            "notes": notes
        }), 200
    except Exception as e:
        notes.append(f"probe_error: {e!s}")
        return jsonify({"ok": False, "hybrid_available": False, "notes": notes}), 200

@rag_bp.post("/hybrid/search")
def api_search():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    query = _norm_query(payload)
    top_k = _norm_top_k(payload, default=6)
    include_text = _coerce_bool(payload.get("include_text"))  # None = ne vmeshivaemsya
    max_chars = _coerce_int(payload.get("max_chars"), default=None)

    hybrid_search, err = _import_hybrid()
    if hybrid_search is None:
        return jsonify({"ok": False, "error": "hybrid retriever unavailable"}), 503

    # soberem tolko «chistye» kwargs + nashi normalizovannye flagi (esli zadany)
    kwargs = _clean_payload(payload)
    if include_text is not None:
        kwargs["include_text"] = include_text
    if max_chars is not None:
        kwargs["max_chars"] = max_chars

    try:
        res = hybrid_search(query=query, top_k=top_k, **kwargs)
        hits = res.get("hits") or res.get("items") or []
        return jsonify({
            "ok": True,
            "query_echo": query,
            "hits": hits,
            "items": res.get("items", hits),
            "counts": {"total": len(hits)},
            "backend": res.get("backend"),
            "docs_path": res.get("docs_path"),
            "count_indexed": res.get("count_indexed"),
            "max_chars": res.get("max_chars"),
            "include_text": res.get("include_text"),
            "judge_used": False
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def register(app):
    app.register_blueprint(rag_bp)
    return app