# -*- coding: utf-8 -*-
"""
routes/desktop_driver_routes.py - REST/UI dlya drayvera rabochego stola.

Ruchki:
  GET  /desktop/driver/probe
  GET  /desktop/driver/whitelist
  POST /desktop/driver/whitelist/add   {"name":"TextEdit","cmd":"/System/Applications/TextEdit.app","kind":"app"}
  POST /desktop/driver/whitelist/remove{"name":"TextEdit","kind":"app"}
  POST /desktop/driver/plan_to_commands {"plan":[...]}
  POST /desktop/driver/execute         {"plan":[...], "dry_run":true}
  GET  /admin/desktop_driver

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.agents import desktop_os_driver as DD
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("desktop_driver_routes", __name__, url_prefix="/desktop/driver")

@bp.route("/probe", methods=["GET"])
def probe():
    return jsonify(DD.probe())

@bp.route("/whitelist", methods=["GET"])
def whitelist():
    return jsonify(DD.whitelist_get())

@bp.route("/whitelist/add", methods=["POST"])
def wl_add():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify(DD.whitelist_add(d.get("name",""), d.get("cmd",""), d.get("kind","app")))

@bp.route("/whitelist/remove", methods=["POST"])
def wl_remove():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify(DD.whitelist_remove(d.get("name",""), d.get("kind","app")))

@bp.route("/plan_to_commands", methods=["POST"])
def plan_to_commands():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify({"ok":True,"items": DD.plan_to_commands(d.get("plan") or [])})

@bp.route("/execute", methods=["POST"])
def execute():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify(DD.execute(d.get("plan") or [], bool(d.get("dry_run", True))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_desktop_driver.html")

def register(app):
    app.register_blueprint(bp)