# -*- coding: utf-8 -*-
"""
routes/admin_portable_files.py — prosmotr faylov portable kataloga (read-only).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

from flask import Blueprint, jsonify, request

bp = Blueprint("admin_portable_files", __name__)

def _root() -> Path:
    root = os.getenv("ESTER_PORTABLE_DIR") or os.path.join("data", "portable")
    return Path(root).resolve()

def _safe_path(rel: str) -> Path:
    base = _root()
    p = (base / rel).resolve()
    if not str(p).startswith(str(base)):
        raise ValueError("path traversal")
    return p

@bp.get("/admin/portable/files")
def list_files():
    rel = (request.args.get("path") or "").strip()
    try:
        p = _safe_path(rel) if rel else _root()
    except Exception:
        return jsonify({"ok": False, "error": "bad path"}), 400
    if not p.exists():
        return jsonify({"ok": False, "error": "not found"}), 404
    if p.is_file():
        return jsonify({"ok": True, "path": rel, "items": []})
    items: List[Dict[str, str]] = []
    for child in sorted(p.iterdir(), key=lambda x: x.name.lower()):
        try:
            items.append({
                "name": child.name,
                "type": "dir" if child.is_dir() else "file",
            })
        except Exception:
            pass
    return jsonify({"ok": True, "path": rel, "items": items})

@bp.get("/admin/portable/files/read")
def read_file():
    rel = (request.args.get("path") or "").strip()
    if not rel:
        return jsonify({"ok": False, "error": "path required"}), 400
    try:
        p = _safe_path(rel)
    except Exception:
        return jsonify({"ok": False, "error": "bad path"}), 400
    if not p.exists() or not p.is_file():
        return jsonify({"ok": False, "error": "not found"}), 404
    max_kb = max(1, int(os.getenv("PORTABLE_READ_MAX_KB", "256")))
    data = p.read_bytes()[: max_kb * 1024]
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        text = ""
    return jsonify({"ok": True, "path": rel, "text": text, "truncated": len(data) >= max_kb * 1024})

def register(app):
    app.register_blueprint(bp)
    return app
