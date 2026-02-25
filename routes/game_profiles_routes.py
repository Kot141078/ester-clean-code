# -*- coding: utf-8 -*-
"""routes/game_profiles_routes.py - upravlenie profilnym slovarem igr/prilozheniy.

Ruchki:
  GET /games/profiles/list -> {ok, profiles}
  POST /games/profiles/install {"name":..} -> {ok}
  POST /games/profiles/bind {"title":"Diablo","profile":"FPS_basic"} -> {ok}
  POST /games/profiles/apply_hotkeys {"title":"Diablo"} -> poslat nabor khotkeev v tselevoe okno (po privyazke)

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict
from modules.thinking.game_profiles import list_profiles, install_preset, bind_profile, get_binding_for
from modules.ops.window_ops import focus_by_title, send_hotkey
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("game_profiles_routes", __name__, url_prefix="/games/profiles")

@bp.route("/list", methods=["GET"])
def lst():
    return jsonify({"ok": True, "profiles": list_profiles()})

@bp.route("/install", methods=["POST"])
def install():
    name = (request.get_json(force=True, silent=True) or {}).get("name","")
    return jsonify(install_preset(name))

@bp.route("/bind", methods=["POST"])
def bindp():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(bind_profile((data.get("title") or ""), (data.get("profile") or "")))

@bp.route("/apply_hotkeys", methods=["POST"])
def apply_hotkeys():
    data = request.get_json(force=True, silent=True) or {}
    title = (data.get("title") or "").strip()
    b = get_binding_for(title or "")
    if not b:
        return jsonify({"ok": False, "error": "binding_not_found"}), 404
    focus_by_title(b["title"])
    sent = []
    for seq in b["spec"].get("hotkeys", []):
        ok = send_hotkey(seq)
        sent.append({"seq": seq, "ok": bool(ok)})
    return jsonify({"ok": True, "sent": sent, "pace": b["spec"].get("pace","human_norm")})


def register(app):
    app.register_blueprint(bp)
    return app