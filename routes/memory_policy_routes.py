# -*- coding: utf-8 -*-
"""routes/memory_policy_routes.py - REST/UI dlya politik pamyati.

Ruchki:
  GET /memory/policy/config
  POST /memory/policy/config { retention_days:{...}, privacy:{...}, compaction:{...}, automod:{...} }
  POST /memory/policy/retention { dry_run: true|false }
  POST /memory/policy/scan_pii
  POST /memory/policy/scrub_now { ids: [..] }
  POST /memory/policy/compact { dry_run: true|false }
  GET /memory/policy/export_scrubbed
  POST /memory/policy/automod_tick
  GET /admin/memory_policies

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.memory import policies
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("memory_policy_routes", __name__, url_prefix="/memory/policy")

@bp.route("/config", methods=["GET"])
def cfg_get():
    return jsonify({"ok": True, "config": policies.config_get()})

@bp.route("/config", methods=["POST"])
def cfg_set():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify({"ok": True, "config": policies.config_set(d)})

@bp.route("/retention", methods=["POST"])
def retention():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(policies.apply_retention(bool(d.get("dry_run", True))))

@bp.route("/scan_pii", methods=["POST"])
def scan():
    return jsonify(policies.scan_pii())

@bp.route("/scrub_now", methods=["POST"])
def scrub():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(policies.scrub_now(d.get("ids")))

@bp.route("/compact", methods=["POST"])
def compact():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(policies.compact(bool(d.get("dry_run", True))))

@bp.route("/export_scrubbed", methods=["GET"])
def export_scrubbed():
    return jsonify(policies.export_scrubbed(apply_ret=True))

@bp.route("/automod_tick", methods=["POST"])
def automod():
    return jsonify(policies.automod_tick())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_memory_policies.html")

def register(app):
    app.register_blueprint(bp)