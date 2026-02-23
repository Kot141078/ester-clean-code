# -*- coding: utf-8 -*-
"""
routes/lexicon_routes.py - REST/UI dlya slovarya UI-leksiki.

Ruchki:
  POST /lexicon/mine    {"N":500}
  POST /lexicon/merge   {"candidates":[...]}
  GET  /lexicon/preview {"top":200}
  GET  /lexicon/export
  GET  /admin/lexicon

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.ocr.lexicon_builder import mine_from_journal, merge_guess, preview, export_json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("lexicon_routes", __name__, url_prefix="/lexicon")

@bp.route("/mine", methods=["POST"])
def m():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify(mine_from_journal(int(d.get("N",500))))

@bp.route("/merge", methods=["POST"])
def mg():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify(merge_guess(list(d.get("candidates") or [])))

@bp.route("/preview", methods=["GET"])
def p():
    return jsonify(preview(int(request.args.get("top",200))))

@bp.route("/export", methods=["GET"])
def e():
    return jsonify(export_json())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_lexicon.html")

def register(app):
    app.register_blueprint(bp)