# modules/rag/rag_http.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

# Lokalnye importy: derzhim nezavisimost ot "hub"
from modules.rag import file_readers as fr
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

rag_bp = Blueprint("rag_docs_bp", __name__, url_prefix="/ester/rag/docs")


# ---------- utility ----------

def _env_bool(*keys: str, default: bool = False) -> bool:
    """We read a set of possible flag keys. Any true value => Three."""
    truthy = {"1", "true", "yes", "on", "y", "t"}
    for k in keys:
        v = os.getenv(k, "")
        if v and v.strip().lower() in truthy:
            return True
    return default


def _resolve_base_path(candidate: Optional[str]) -> str:
    """We bring the path to the string, expand ZZF0ZZAR% / $VAR / ~, normalizes slashes.
    We don’t touch anything at the permissions level—we just calculate the correct path."""
    if not candidate:
        return ""
    # First expandvars, then expandoser. The input is always a string.
    s = str(candidate)
    s = os.path.expandvars(s)
    s = os.path.expanduser(s)
    # Normalizuem. Pod Win vernem backslashes, pod *nix — forvardy.
    return os.path.normpath(s)


def _get_docs_base_from_env() -> str:
    """Sobiraem kandidatov iz neskolkikh klyuchey; pervyy suschestvuyuschiy - pobeditel.
    Esli nichego ne nashlos, vernem prosto normalizovannyy put iz pervogo klyucha."""
    keys = [
        "ESTER_RAG_FORCE_PATH",
        "RAG_DOCS_PATH",
        "ESTER_RAG_DOCS_PATH",
        "ESTER_RAG_DOCS_DIR",
        "ESTER_DOCS_DIR",
    ]
    resolved: Dict[str, str] = {}
    for k in keys:
        path = _resolve_base_path(os.getenv(k, ""))
        if path:
            resolved[k] = path
            if os.path.isdir(path):
                return path
    # false: if none exists, but at least there was something, return the first non-empty one
    for k in keys:
        if resolved.get(k):
            return resolved[k]
    # finalnyy zapasnoy: ~/.ester/docs
    fallback = os.path.normpath(os.path.expandvars(os.path.expanduser(os.path.join("~", ".ester", "docs"))))
    return fallback


def _ingest_allowed() -> bool:
    """Edinaya tochka prinyatiya resheniya: vklyuchen li RAG voobsche i imenno HTTP-ingest.
    Daem shirokiy “belyy spisok” klyuchey, chtoby ne zaviset ot konkretnogo imeni."""
    return _env_bool(
        "ESTER_RAG_ENABLE",
        "RAG_ENABLE",
        "ESTER_RAG_HTTP_ENABLE",
        "RAG_HTTP_ENABLE",
        "ESTER_RAG_INGEST_ENABLE",
        "RAG_INGEST_ENABLE",
        default=False,
    )


# ---------- marshruty ----------

@rag_bp.get("/status")
def status() -> Any:
    try:
        debug = fr.debug_status() if hasattr(fr, "debug_status") else {}
    except Exception as e:
        debug = {"error": f"{type(e).__name__}: {e}"}

    # Shows what the HTTP layer will see, and not just the file_reader
    http_view = {
        "http_ingest_allowed": _ingest_allowed(),
        "http_docs_base": _get_docs_base_from_env(),
    }

    return jsonify({"ok": True, "debug": debug, "http": http_view})


@rag_bp.post("/ingest")
def ingest() -> Any:
    if not _ingest_allowed():
        return jsonify({"ok": False, "reason": "rag_disabled"}), 400

    # Istochnik puti: query ?path=..., libo body {path:"..."},
    # libo berem iz okruzheniya (sm. _get_docs_base_from_env)
    path = request.args.get("path") or (request.get_json(silent=True) or {}).get("path")
    base = _get_docs_base_from_env() if not path else _resolve_base_path(path)

    tag = (request.get_json(silent=True) or {}).get("tag") or "local_docs"
    reindex = (request.get_json(silent=True) or {}).get("reindex")

    try:
        # file_readers: use the widest possible entry point
        if hasattr(fr, "ingest_base"):
            res = fr.ingest_base(base=base, tag=tag, reindex=reindex)
        elif hasattr(fr, "ingest_dir"):
            res = fr.ingest_dir(base, tag=tag, reindex=reindex)
        else:
            return jsonify({"ok": False, "reason": "no_ingest_entry_in_file_readers"})

        # Normalizes the response
        if not isinstance(res, dict):
            res = {"ok": True, "total": 0, "ingested": 0, "note": "non-dict result from file_readers", "result": str(res)}

        res.setdefault("ok", True)
        res.setdefault("base", base)
        res.setdefault("tag", tag)
        return jsonify(res)
    except PermissionError as e:
        return jsonify({"ok": False, "base": base, "tag": tag, "reason": f"permission_error:{e}"}), 400
    except Exception as e:
        return jsonify({"ok": False, "base": base, "tag": tag, "reason": f"ingest_exception:{type(e).__name__}:{e}"}), 500