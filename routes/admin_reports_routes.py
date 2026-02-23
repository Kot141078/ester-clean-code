# -*- coding: utf-8 -*-
"""Admin reports endpoints."""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from flask import Blueprint, jsonify, render_template

admin_reports_bp = Blueprint("admin_reports_json_routes", __name__, url_prefix="/admin/reports")


def _read_json(path: str) -> Dict[str, Any]:
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


@admin_reports_bp.get("/")
def admin_reports_page():
    try:
        return render_template("admin_reports.html")
    except Exception:
        return (
            "<html><body><h3>Admin Reports</h3><p>No template.</p></body></html>",
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )


@admin_reports_bp.get("/json")
def admin_reports_json():
    base = os.getenv("PERSIST_DIR") or os.path.join(os.getcwd(), "data")
    return jsonify(
        {
            "ok": True,
            "dreams": _read_json(os.path.join(base, "dreams", "last_report.json")),
            "gc": _read_json(os.path.join(base, "gc", "last_report.json")),
            "rebuild": _read_json(os.path.join(base, "reports", "last_report.json")),
        }
    )


def register_admin_reports_routes(app):
    # Idempotentnost po pravilu, a ne po imeni blueprint (v proekte uzhe est drugoy admin_reports).
    if any(r.rule == "/admin/reports/json" for r in app.url_map.iter_rules()):
        return app
    app.register_blueprint(admin_reports_bp)
    return app


def register(app):
    return register_admin_reports_routes(app)
