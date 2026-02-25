# -*- coding: utf-8 -*-
"""routes/quest_routes.py - REST/UI dlya "uchebnykh kvestov".

Ruchki:
  POST /quests/mine {"N":300}
  GET /quests/preview
  GET /quests/export
  GET /admin/quests

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.learn.quest_generator import mine, preview, export
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("quest_routes", __name__, url_prefix="/quests")

@bp.route("/mine", methods=["POST"])
def m():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(mine(int(data.get("N", 300))))

@bp.route("/preview", methods=["GET"])
def p():
    return jsonify(preview())

@bp.route("/export", methods=["GET"])
def e():
    return jsonify(export())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_quests.html")

def register(app):
    app.register_blueprint(bp)