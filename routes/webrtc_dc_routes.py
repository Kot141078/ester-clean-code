# -*- coding: utf-8 -*-
"""routes/webrtc_dc_routes.py - REST/SSE dlya psevdo-DataChannel.

Ruchki:
  POST /webrtc/dc/open {"room":"id","client":"alice"}
  GET /webrtc/dc/recv?room=id&client=alice (SSE)
  POST /webrtc/dc/send {"room":"id","client":"alice","data":{...},"broadcast":true,"target":null}
  POST /webrtc/dc/hb {"room":"id","client":"alice"}
  GET /admin/webrtc

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, Response, render_template
from modules.webrtc.datachannel_stub import open_room, send, drain, heartbeat, gc
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("webrtc_dc_routes", __name__, url_prefix="/webrtc/dc")

@bp.route("/open", methods=["POST"])
def open_():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(open_room(str(data.get("room","")), str(data.get("client",""))))

@bp.route("/hb", methods=["POST"])
def hb():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(heartbeat(str(data.get("room","")), str(data.get("client",""))))

@bp.route("/send", methods=["POST"])
def send_():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(send(str(data.get("room","")), str(data.get("client","")), data.get("data"), bool(data.get("broadcast", True)), data.get("target")))

@bp.route("/recv", methods=["GET"])
def recv():
    room = request.args.get("room",""); client = request.args.get("client","")
    def gen():
        # Simple CCE loop
        while True:
            msgs = drain(room, client)
            for m in msgs:
                yield f"data: {m}\n\n"
            gc()
            time.sleep(0.2)
    return Response(gen(), mimetype="text/event-stream")

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_webrtc.html")

def register(app):
    app.register_blueprint(bp)