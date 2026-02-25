# -*- coding: utf-8 -*-
"""routes/memory_timeline_routes.py - REST/UI dlya lenty pamyati.

Ruchki:
  GET /memory/timeline
      ?q=...&type=dialog|event|fact|dream|goal&source=web|telegram|file|thought
      &start=unix_ts&end=unix_ts&limit=500&offset=0
  GET /memory/timeline/export (te zhe parameter - otdaet JSON)
  GET /admin/memory_timeline

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.memory.timeline import build_timeline, export_timeline
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("memory_timeline_routes", __name__, url_prefix="/memory")

@bp.route("/timeline", methods=["GET"])
def timeline():
    q = request.args.get("q", "").strip()
    type_ = request.args.get("type")
    source = request.args.get("source")
    start = request.args.get("start")
    end = request.args.get("end")
    limit = int(request.args.get("limit", 500))
    offset = int(request.args.get("offset", 0))
    start_ts = int(start) if start and start.isdigit() else None
    end_ts = int(end) if end and end.isdigit() else None
    data = build_timeline(start_ts, end_ts, type_, source, q, limit, offset)
    return jsonify(data)

@bp.route("/timeline/export", methods=["GET"])
def timeline_export():
    q = request.args.get("q", "").strip()
    type_ = request.args.get("type")
    source = request.args.get("source")
    start = request.args.get("start")
    end = request.args.get("end")
    limit = int(request.args.get("limit", 10000))
    start_ts = int(start) if start and start.isdigit() else None
    end_ts = int(end) if end and end.isdigit() else None
    data = export_timeline(start_ts, end_ts, type_, source, q, limit)
    return jsonify(data)

@bp.route("/admin/memory_timeline", methods=["GET"])
def admin():
    return render_template("admin_memory_timeline.html")

def register(app):
    app.register_blueprint(bp)