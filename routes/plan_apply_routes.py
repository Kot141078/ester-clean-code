# -*- coding: utf-8 -*-
"""
routes/plan_apply_routes.py - REST/UI dlya primeneniya «plana shablonov».

Ruchki:
  POST /trigger_plan/dry_run {"plan":[...], "batch":50}
  POST /trigger_plan/apply   {"plan":[...], "batch":50}
  GET  /admin/trigger_plan

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.triggers.plan_apply import dry_run, apply
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("plan_apply_routes", __name__, url_prefix="/trigger_plan")

@bp.route("/dry_run", methods=["POST"])
def dr():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(dry_run(list(d.get("plan") or []), int(d.get("batch",50))))

@bp.route("/apply", methods=["POST"])
def ap():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(apply(list(d.get("plan") or []), int(d.get("batch",50))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_trigger_plan.html")

def register(app):
    app.register_blueprint(bp)