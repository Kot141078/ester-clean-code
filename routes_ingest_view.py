# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def register_ingest_view_routes(app, vstore, url_prefix: str = "/ingest_view"):
    bp = Blueprint("ingest_view", __name__)

    @bp.get(url_prefix + "/list")
    @jwt_required()
    def ingest_list():
        return jsonify({"docs": vstore.size()})

    @bp.get(url_prefix + "/job")
    @jwt_required()
    def ingest_job():
        jid = request.args.get("id", "") or ""
        ing = getattr(app, "ingest", None)
        if not ing:
            return jsonify({"error": "ingest not available"}), 503
        if not jid:
            return jsonify({"error": "id required"}), 400
        job = ing.get_job(jid)  # type: ignore
        if not job:
            return jsonify({"error": "not found"}), 404
        return jsonify(job)

    app.register_blueprint(bp)


def register_ingest_routes(app, ingest, url_prefix: str = "/ingest"):
    """
    Dopolnitelnye «servisnye» marshruty dlya inzhesta:
      - POST /ingest/submit {path}
      - GET  /ingest/jobs
    """
    bp = Blueprint("ingest_more", __name__)

    @bp.post(url_prefix + "/submit")
    @jwt_required()
    def ingest_submit():
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        path = (data.get("path") or "").strip()
        if not path:
            return jsonify({"error": "path required"}), 400
        jid = ingest.submit_file(path)
        return jsonify({"id": jid, "status": "QUEUED"})

    @bp.get(url_prefix + "/jobs")
    @jwt_required()
    def ingest_jobs():
        return jsonify({"items": ingest.list_jobs()})

# app.register_blueprint(bp)