# -*- coding: utf-8 -*-
"""routes/demo_installer_routes.py - UI/REST dlya vklyucheniya “rezhima demonstratsii”.

Ruchki:
  POST /demo/install -> bystryy komplekt presetov + guard + playlist
  POST /demo/play/notepad -> nebolshoy progon missii notepad_intro
  POST /demo/export -> eksport tekuschego gayda (PNG+SRT+skripty)
  GET /admin/demo -> panel

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.admin.demo_installer import quick_install, play_notepad_intro, export_current_guide
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("demo_installer_routes", __name__, url_prefix="/demo")

@bp.route("/install", methods=["POST"])
def install():
    return jsonify(quick_install())

@bp.route("/play/notepad", methods=["POST"])
def play_notepad():
    return jsonify(play_notepad_intro())

@bp.route("/export", methods=["POST"])
def export():
    return jsonify(export_current_guide())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_demo.html")

def register(app):
    app.register_blueprint(bp)