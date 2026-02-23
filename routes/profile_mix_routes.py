# -*- coding: utf-8 -*-
"""
routes/profile_mix_routes.py - upravlenie miksami profiley.

Ruchki:
  POST /profiles/mix/create {"name":"mix_fps","layers":["FPS_basic","Editor_notepad"]}
  GET  /profiles/mix/get    ?name=mix_fps
  POST /profiles/mix/bind   {"title":"Notepad","mix":"mix_fps"}
  POST /profiles/mix/apply  {"title":"Notepad"}     # primenyaet miks ili profil (fallback)

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.thinking.profile_mix import create_mix, get_mix, bind_mix, apply_for_title
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("profile_mix_routes", __name__, url_prefix="/profiles/mix")

@bp.route("/create", methods=["POST"])
def create():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(create_mix(data.get("name",""), list(data.get("layers") or [])))

@bp.route("/get", methods=["GET"])
def get():
    name = (request.args.get("name") or "")
    return jsonify(get_mix(name))

@bp.route("/bind", methods=["POST"])
def bind():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(bind_mix(data.get("title",""), data.get("mix","")))

@bp.route("/apply", methods=["POST"])
def apply():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(apply_for_title(data.get("title","")))

def register(app):
    app.register_blueprint(bp)