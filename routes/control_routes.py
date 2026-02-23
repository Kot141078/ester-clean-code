# -*- coding: utf-8 -*-
"""
routes/control_routes.py - «pauza/SOS» i status.

Ruchki:
  GET  /control/status           -> {ok, paused}
  POST /control/pause            -> {ok, paused:true}
  POST /control/resume           -> {ok, paused:false}

Integratsiya: v kode marshrutov deystviy pered vypolneniem proveryayte control_state.get_paused()
i pri True vozvraschayte 423 Locked + {error:"paused"}.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.ops.control_state import get_paused, set_paused
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("control_routes", __name__, url_prefix="/control")

@bp.route("/status", methods=["GET"])
def status():
    return jsonify({"ok": True, "paused": get_paused()})

@bp.route("/pause", methods=["POST"])
def pause():
    set_paused(True)
    return jsonify({"ok": True, "paused": True})

@bp.route("/resume", methods=["POST"])
def resume():
    set_paused(False)
    return jsonify({"ok": True, "paused": False})

def register(app):
    app.register_blueprint(bp)