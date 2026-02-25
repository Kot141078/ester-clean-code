# -*- coding: utf-8 -*-
"""routes/policy_routes.py - REST/UI dlya politik.

Ruchki:
  GET /policy/list
  POST /policy/save { ...polnyy obekt politik... }
  POST /policy/decide {"agent":"desktop","kind":"click","subject":"user:default","meta":{...},"safety":"allow","ctx":{"mode":"A","real_enabled":false,"requires_admin":false,"steps":3}}
  GET /admin/policies

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.policy import engine as PE
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("policy_routes", __name__, url_prefix="/policy")

@bp.route("/list", methods=["GET"])
def list_():
    return jsonify(PE.list_all())

@bp.route("/save", methods=["POST"])
def save():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify(PE.save_all(d))

@bp.route("/decide", methods=["POST"])
def decide():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify(PE.evaluate(
        d.get("agent","desktop"),
        d.get("kind","open_app"),
        d.get("meta") or {},
        d.get("subject","user:default"),
        d.get("safety","allow"),
        d.get("ctx") or {}
    ))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_policies.html")

def register(app):
    app.register_blueprint(bp)