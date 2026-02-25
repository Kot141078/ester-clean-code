# -*- coding: utf-8 -*-
from __future__ import annotations
"""routes/garage_pipeline_routes.py - REST-kontur Garage/Workbench
(konveyer: poisk → skoring → generatsiya → autrich → billing → otchet)

Mosty (yavnyy):
  • (Garage/Workbench ↔ REST) - edinye ruchki upravleniya konveyerom v stile Ester.

Skrytye mosty:
  • (Portfolio/affekt ↔ Prioritezatsiya) - skoring uchityvaet navyki/byudzhet/dedlayn; legko podmeshat affect-boost.
  • (Billing ↔ UI/Otchety) - invoysy i otchety kladutsya v faylovuyu ierarkhiyu + dostupny po REST.

Zemnoy abzats:
Eto “panel stanka”: knopki Start/Skan/Otchet, kotorye dergayut nastoyaschie mekhanizmy konveyera.

ENV (optional): sm. modules/garage/pipeline.py

# c=a+b"""
from datetime import date
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore

from modules.garage.pipeline import (
    daily_report,
    generate_project,
    run_pipeline,
    scan_jobs,
    send_outreach,
)

garage_pipeline_bp = Blueprint("garage_pipeline", __name__, url_prefix="/garage/pipeline")


@garage_pipeline_bp.get("/jobs/scan")
@jwt_required(optional=True)
def api_scan_jobs():
    jobs = scan_jobs()
    return jsonify({"ok": True, "count": len(jobs), "jobs": jobs})


@garage_pipeline_bp.post("/run")
@jwt_required(optional=True)
def api_run_pipeline():
    """JSON-parameter (lyuboy iz variantov):
      - {"job": {...}} - syroe opisanie brifa
      - {"job_id": "<id>"} - iz rezultatov /jobs/scan
      - {"auto": true} - vzyat luchshiy po skoru"""
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    result = run_pipeline(data)
    code = 200 if result.get("ok") else 500
    return jsonify(result), code


@garage_pipeline_bp.post("/outreach/<job_id>")
@jwt_required(optional=True)
def api_outreach(job_id: str):
    res = send_outreach(job_id)
    code = 200 if res.get("ok") else 500
    return jsonify(res), code


@garage_pipeline_bp.get("/report/daily")
@jwt_required(optional=True)
def api_daily_report():
    d = request.args.get("date") or date.today().isoformat()
    fmt = (request.args.get("fmt") or "json").lower()
    rpt = daily_report(d)
    if fmt == "json":
        return jsonify(rpt)
    # Simple DSV (top summary level only)
    lines = ["metric,value"]
    for k, v in rpt.get("summary", {}).items():
        lines.append(f"{k},{v}")
    return ("\n".join(lines), 200, {"Content-Type": "text/csv"})


def register_garage_pipeline_routes(app) -> None:
    """Standard blueprint registration (picked up by the general route registry)."""
    app.register_blueprint(garage_pipeline_bp)


def register(app):
    app.register_blueprint(garage_pipeline_bp)
    return app
