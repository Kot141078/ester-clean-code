# -*- coding: utf-8 -*-
"""routes/adaptive_quota_routes.py - REST/UI dlya adaptivnykh kvot.

Ruchki:
  POST /adaptive_quota/config {"room":"r","qmin":2,"qmax":15,"k":2.0}
  POST /adaptive_quota/hb {"room":"r","client":"bob","rtt_ms":85}
  GET /adaptive_quota/quotas?room=r
  GET /adaptive_quota/status?room=r
  GET /admin/adaptive_quota

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.coop.adaptive_quota import config, heartbeat, quotas, status
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("adaptive_quota_routes", __name__, url_prefix="/adaptive_quota")

@bp.route("/config", methods=["POST"])
def cfg():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(config(str(d.get("room","")), int(d.get("qmin",2)), int(d.get("qmax",15)), float(d.get("k",2.0))))

@bp.route("/hb", methods=["POST"])
def hb():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(heartbeat(str(d.get("room","")), str(d.get("client","")), float(d.get("rtt_ms",50))))

@bp.route("/quotas", methods=["GET"])
def q():
    return jsonify(quotas(str(request.args.get("room",""))))

@bp.route("/status", methods=["GET"])
def s():
    return jsonify(status(str(request.args.get("room",""))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_adaptive_quota.html")

def register(app):
    app.register_blueprint(bp)