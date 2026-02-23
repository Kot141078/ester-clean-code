# -*- coding: utf-8 -*-
"""
routes/admin_portable_metrics.py — prostye metriki portable okruzheniya.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

from flask import Blueprint, jsonify

bp = Blueprint("admin_portable_metrics", __name__)

def _portable_root() -> Path:
    root = os.getenv("ESTER_PORTABLE_DIR") or os.path.join("data", "portable")
    return Path(root)

def _scan_metrics() -> Dict[str, int]:
    root = _portable_root()
    total_files = 0
    total_bytes = 0
    if root.exists():
        for p in root.rglob("*"):
            try:
                if p.is_file():
                    total_files += 1
                    total_bytes += p.stat().st_size
            except Exception:
                pass
    return {"files": total_files, "bytes": total_bytes}

@bp.get("/admin/portable/metrics")
def metrics():
    m = _scan_metrics()
    return jsonify({"ok": True, "root": str(_portable_root()), "metrics": m})

@bp.get("/admin/portable/metrics/status")
def status():
    m = _scan_metrics()
    return jsonify({"ok": True, "metrics": m})

def register(app):
    app.register_blueprint(bp)
    return app
