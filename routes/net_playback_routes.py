# -*- coding: utf-8 -*-
"""
routes/net_playback_routes.py - REST/UI dlya setevogo pleybeka.

Ruchki:
  POST /netplay/peers   {"peers":["192.168.1.22:8000"]}
  GET  /netplay/status
  POST /netplay/leader/step   {"step":{...},"index":0}
  POST /netplay/leader/ctrl   {"op":"start|pause|resume|stop|next|prev","index":0?}
  POST /netplay/ingest  {"cmd":"step|control", ...}    # vedomyy prinimaet paket
  GET  /admin/netplay

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.coop.net_playback import set_peers, status as st, leader_step, leader_control, follower_ingest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("net_playback_routes", __name__, url_prefix="/netplay")

@bp.route("/peers", methods=["POST"])
def peers():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(set_peers(list(data.get("peers") or [])))

@bp.route("/status", methods=["GET"])
def status():
    return jsonify(st())

@bp.route("/leader/step", methods=["POST"])
def lstep():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(leader_step(data.get("step") or {}, int(data.get("index", 0))))

@bp.route("/leader/ctrl", methods=["POST"])
def lctrl():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(leader_control((data.get("op") or ""), data.get("index", None)))

@bp.route("/ingest", methods=["POST"])
def ingest():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(follower_ingest(data))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_netplay.html")

def register(app):
    app.register_blueprint(bp)