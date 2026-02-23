# -*- coding: utf-8 -*-
"""
routes/admin_portable_links.py — spisok ssylok/resursov portable rezhima.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

bp = Blueprint("admin_portable_links", __name__)

def _links_path() -> Path:
    root = os.getenv("ESTER_PORTABLE_DIR") or os.path.join("data", "portable")
    return Path(root) / "links.json"

def _default_links() -> List[Dict[str, Any]]:
    return [
        {"title": "Memory UI", "url": "/memory/admin"},
        {"title": "Providers", "url": "/providers/status"},
        {"title": "Ingest", "url": "/ingest"},
        {"title": "Portable Firststart", "url": "/admin/portable/firststart"},
    ]

def _load_links() -> List[Dict[str, Any]]:
    p = _links_path()
    if not p.exists():
        return _default_links()
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(obj, list):
            return obj
    except Exception:
        pass
    return _default_links()

@bp.get("/admin/portable/links")
def page():
    return jsonify({"ok": True, "items": _load_links()})

@bp.get("/admin/portable/links/list")
def list_links():
    return jsonify({"ok": True, "items": _load_links()})

@bp.post("/admin/portable/links/save")
def save_links():
    body = request.get_json(silent=True) or {}
    items = body.get("items") or []
    if not isinstance(items, list):
        return jsonify({"ok": False, "error": "items must be list"}), 400
    p = _links_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "count": len(items)})

def register(app):
    app.register_blueprint(bp)
    return app
