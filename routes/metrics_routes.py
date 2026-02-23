# -*- coding: utf-8 -*-
"""
routes/metrics_routes.py - metriki payplayna (JSON + prostaya HTML-panel).

# c=a+b
"""
from __future__ import annotations
import os, json
from typing import Any, Dict
from flask import Blueprint, jsonify, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("metrics_routes", __name__)

def _read(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

@bp.get("/metrics")
def metrics_json():
    base = os.getenv("DATA_DIR") or os.path.join(os.getcwd(), "data")
    out: Dict[str, Any] = {
        "jobs": _read(os.path.join(base, "jobs.json")),
        "metrics_dedup": _read(os.path.join(base, "metrics_dedup.json")),
        "answer_cache_stats": _read(os.path.join(base, "answer_cache_stats.json")),
    }
    return jsonify({"ok": True, **out})

@bp.get("/metrics/html")
def metrics_html():
    try:
        return render_template("metrics.html")
    except Exception:
        return "<html><body><h3>Metrics</h3><p>Template missing.</p></body></html>"

def register(app) -> None:
    if bp.name in getattr(app, "blueprints", {}):
        return
    app.register_blueprint(bp)


def register(app):
    app.register_blueprint(bp)
    return app