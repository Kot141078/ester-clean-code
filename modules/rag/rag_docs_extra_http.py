# -*- coding: utf-8 -*-
"""
Dop. routy dlya RAG-dokov:
  GET  /ester/rag/docs/status      — svodka putey/flagov
  POST /ester/rag/docs/grep        — tochnyy poisk podstroki po faylam (utf-8)
  POST /ester/rag/docs/quote_once  — vernut pervuyu tochnuyu stroku (dlya chat-mosta)

VNIMANIE: bez Flask-vnutrennikh test_request_context. Vsya logika vynesena v chistye khelpery.
"""
import os
from typing import List, Dict, Optional
from flask import Blueprint, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("rag_docs_extra", __name__)

# ------------------------- obschie khelpery (bez Flask) -------------------------

def _expand(p: str) -> str:
    """expandvars + abspath; ustoychivo k pustym znacheniyam."""
    return os.path.abspath(os.path.expandvars(p)) if p else ""

def _docs_base() -> str:
    base = (os.getenv("ESTER_RAG_FORCE_PATH")
            or os.getenv("ESTER_RAG_DOCS_DIR")
            or os.getenv("RAG_DOCS_PATH")
            or os.getenv("ESTER_RAG_DOCS_PATH")
            or os.getenv("ESTER_DOCS_DIR")
            or r"%USERPROFILE%\.ester\docs")
    base = _expand(base)
    return base

_ALLOW_EXT = {".txt", ".md", ".rst", ".log", ".json", ".cfg", ".ini", ".yaml", ".yml"}

def grep_in_docs(pattern: str, limit: int = 50) -> Dict:
    """
    Det. poisk podstroki po dopustimym tekstovym faylam v docs base.
    Vozvraschaet dict-peyload kak u starogo grep-routa.
    """
    pattern = (pattern or "").strip()
    base = _docs_base()
    if not pattern:
        return {"ok": False, "error": "empty pattern"}
    if not os.path.isdir(base):
        return {"ok": False, "error": f"base not found: {base}"}

    matches: List[Dict] = []
    for root, _, files in os.walk(base):
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if _ALLOW_EXT and ext not in _ALLOW_EXT:
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if pattern in line:
                            matches.append({"file": path, "line_no": i, "line": line.rstrip("\n")})
                            if len(matches) >= limit:
                                break
            except Exception:
                # tikho propuskaem bitye/zakrytye fayly
                continue
        if len(matches) >= limit:
            break

    return {
        "ok": True,
        "count": len(matches),
        "base": base,
        "pattern": pattern,
        "matches": matches,
    }

def find_first_line(pattern: str) -> Optional[str]:
    """
    Vernut pervuyu tochnuyu stroku (symbol-to-symbol) ili None.
    """
    payload = grep_in_docs(pattern, limit=1)
    if not payload.get("ok"):
        return None
    if payload.get("count", 0) < 1:
        return None
    return payload["matches"][0]["line"]

# ------------------------------ HTTP-routy -----------------------------------

@bp.route("/ester/rag/docs/status", methods=["GET"])
def rag_docs_status():
    base = _docs_base()
    vector_dir_env = os.getenv("ESTER_VECTOR_DIR", "")
    vector_dir = _expand(vector_dir_env) if vector_dir_env else ""
    return jsonify({
        "ok": True,
        "rag_enabled": os.getenv("ESTER_RAG_ENABLE") == "1",
        "base": base,
        "exists": os.path.isdir(base),
        "vector_db": os.getenv("ESTER_VECTOR_DB", ""),
        "vector_dir": vector_dir,
    })

@bp.route("/ester/rag/docs/grep", methods=["POST"])
def rag_docs_grep():
    data = request.get_json(silent=True) or {}
    pattern = (data.get("pattern") or data.get("query") or "").strip()
    limit = int(data.get("limit") or 50)
    payload = grep_in_docs(pattern, limit=limit)
    code = 200 if payload.get("ok") else (404 if "base not found" in payload.get("error","") else 400)
    return jsonify(payload), code

@bp.route("/ester/rag/docs/quote_once", methods=["POST"])
def rag_docs_quote_once():
    """
    Vkhod: { "pattern": "...", "wrap": 1|0 }.
    Vozvraschaet pervuyu naydennuyu tochnuyu stroku.
    """
    data = request.get_json(silent=True) or {}
    pattern = (data.get("pattern") or "").strip()
    wrap = bool(int(data.get("wrap") or 1))
    if not pattern:
        return jsonify(ok=False, error="empty pattern"), 400

    line = find_first_line(pattern)
    if not line:
        return jsonify(ok=True, found=False, quote="NOT_FOUND")

    return jsonify(ok=True, found=True, quote=f"\"{line}\"" if wrap else line)

def register(app):
    app.register_blueprint(bp)
    print("[ester-rag-docs-extra/routes] registered /ester/rag/docs/status,/ester/rag/docs/grep,/ester/rag/docs/quote_once")