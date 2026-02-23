# -*- coding: utf-8 -*-
"""
routes/memory_backup_routes.py - REST/UI bekapov pamyati.

Ruchki:
  POST /memory/backup/create {"label":"optional"}
  GET  /memory/backup/list
  POST /memory/backup/verify {"id":"bk-..."}
  POST /memory/backup/restore {"id":"bk-...","mode":"replace|merge"}
  POST /memory/backup/purge {"keep":10,"max_age_days":90}
  POST /memory/backup/auto/start {"period_sec":21600}
  POST /memory/backup/auto/stop {}
  GET  /admin/memory_backups

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.memory import backups
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("memory_backup_routes", __name__, url_prefix="/memory/backup")

@bp.route("/create", methods=["POST"])
def create():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(backups.create_backup(d.get("label")))

@bp.route("/list", methods=["GET"])
def list_():
    return jsonify(backups.list_backups())

@bp.route("/verify", methods=["POST"])
def verify():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(backups.verify_backup(d.get("id","")))

@bp.route("/restore", methods=["POST"])
def restore():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(backups.restore_backup(d.get("id",""), d.get("mode","replace")))

@bp.route("/purge", methods=["POST"])
def purge():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(backups.purge_old(int(d.get("keep",10)), d.get("max_age_days")))

@bp.route("/auto/start", methods=["POST"])
def auto_start():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(backups.auto_schedule(int(d.get("period_sec", 6*3600))))

@bp.route("/auto/stop", methods=["POST"])
def auto_stop():
    return jsonify(backups.auto_stop())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_memory_backups.html")

def register(app):
    app.register_blueprint(bp)