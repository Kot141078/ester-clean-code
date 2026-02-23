# -*- coding: utf-8 -*-
"""
routes/retrieval_router_metrics.py

Endpoints:
  • GET /metrics/retrieval_router     (Prometheus text)
  • GET /telemetry/retrieval_router   (JSON stats)
  • GET /metrics/retrieval_router_snapshots.jsonl
  • GET /metrics/retrieval_router_snapshots.csv
  • POST /metrics/retrieval_router_snapshot_now
"""
from __future__ import annotations

import os
from flask import Blueprint, jsonify, send_file, request

bp_rr = Blueprint("retrieval_router_metrics", __name__)

try:
    from modules.rag.retrieval_router import get_metrics, get_metrics_text  # type: ignore
except Exception:
    get_metrics = None  # type: ignore
    get_metrics_text = None  # type: ignore


@bp_rr.get("/metrics/retrieval_router")
def metrics():
    if get_metrics_text is None:
        return ("retrieval_router_unavailable 1\n", 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})
    return (get_metrics_text(), 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})


@bp_rr.get("/telemetry/retrieval_router")
def telemetry():
    if get_metrics is None:
        return jsonify({"ok": False, "error": "retrieval_router_unavailable"}), 500
    return jsonify({"ok": True, "metrics": get_metrics()})

def _snap_dir() -> str:
    base = (os.getenv("ESTER_STATE_DIR") or os.getenv("ESTER_HOME") or os.getenv("ESTER_ROOT") or os.getcwd()).strip()
    return os.path.join(base, "data", "metrics")

@bp_rr.get("/metrics/retrieval_router_snapshots.jsonl")
def snapshots_jsonl():
    path = os.path.join(_snap_dir(), "retrieval_router_snapshots.jsonl")
    if not os.path.exists(path):
        return jsonify({"ok": False, "error": "snapshots_not_found"}), 404
    return send_file(path, mimetype="application/jsonl", as_attachment=False)

@bp_rr.get("/metrics/retrieval_router_snapshots.csv")
def snapshots_csv():
    path = os.path.join(_snap_dir(), "retrieval_router_snapshots.csv")
    if not os.path.exists(path):
        return jsonify({"ok": False, "error": "snapshots_not_found"}), 404
    return send_file(path, mimetype="text/csv", as_attachment=False)

@bp_rr.post("/metrics/retrieval_router_snapshot_now")
def snapshot_now():
    try:
        from modules.rag.retrieval_router import snapshot_metrics_to_memory  # type: ignore
        snapshot_metrics_to_memory()
    except Exception as e:
        return jsonify({"ok": False, "error": f"snapshot_failed:{e}"}), 500
    return jsonify({"ok": True})


def register(app):
    app.register_blueprint(bp_rr)
    return app
