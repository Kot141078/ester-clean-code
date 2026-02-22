# modules/rag/rag_status_http.py
from __future__ import annotations
import os
from typing import Any, Dict
from flask import Blueprint, jsonify

# bez zavisimosti ot "hub"
from modules.rag import file_readers as fr
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

rag_status_bp = Blueprint("rag_status_bp", __name__, url_prefix="/ester/rag/docs")


def _env_bool(*keys: str, default: bool = False) -> bool:
    truthy = {"1", "true", "yes", "on", "y", "t"}
    for k in keys:
        v = os.getenv(k, "")
        if v and v.strip().lower() in truthy:
            return True
    return default


def _resolve(p: str) -> str:
    if not p:
        return ""
    p = os.path.expandvars(p)
    p = os.path.expanduser(p)
    return os.path.normpath(p)


def _get_docs_base() -> str:
    keys = [
        "ESTER_RAG_FORCE_PATH",
        "RAG_DOCS_PATH",
        "ESTER_RAG_DOCS_PATH",
        "ESTER_RAG_DOCS_DIR",
        "ESTER_DOCS_DIR",
    ]
    resolved: Dict[str, str] = {}
    for k in keys:
        v = _resolve(os.getenv(k, ""))
        if v:
            resolved[k] = v
            if os.path.isdir(v):
                return v
    for k in keys:
        if resolved.get(k):
            return resolved[k]
    # fallback ~/.ester/docs
    return os.path.normpath(os.path.expanduser(os.path.join("~", ".ester", "docs")))


@rag_status_bp.get("/status")
def status() -> Any:
    try:
        dbg = fr.debug_status() if hasattr(fr, "debug_status") else {}
    except Exception as e:
        dbg = {"error": f"{type(e).__name__}: {e}"}

    http_view = {
        "http_ingest_allowed": _env_bool(
            "ESTER_RAG_ENABLE",
            "RAG_ENABLE",
            "ESTER_RAG_HTTP_ENABLE",
            "RAG_HTTP_ENABLE",
            "ESTER_RAG_INGEST_ENABLE",
            "RAG_INGEST_ENABLE",
            default=False,
        ),
        "http_docs_base": _get_docs_base(),
    }
    return jsonify({"ok": True, "debug": dbg, "http": http_view})