# -*- coding: utf-8 -*-
"""routes/agent_loop_routes.py - upravlenie polnotsennym agentnym tsiklom.

Ruchki:
  POST /agent/loop/start {"goal":"...", "interval_sec":5, "max_steps":50, "max_run_sec":120, "idle_break_sec":20}
  POST /agent/loop/stop {}
  POST /agent/loop/tick {} # razovyy takt (dlya otladki)
  GET /agent/loop/status
  GET /admin/agent_loop

Mosty:
- Yavnyy: REST-ruchki → modules.thinking.loop_full (start/stop/status/tick_once).
- Skrytyy #1: (Admin UI ↔ Nablyudaemost) - shablon admin_agent_loop.html dlya ruchnogo kontrolya.
- Skrytyy #2: (Servisnye skripty ↔ API) - stabilnye JSON-kontrakty dlya avtotestov i smoke-skriptov.

Zemnoy abzats:
This is a thin HTTP layer. On ne “dumaet”, a transliruet komandy polzovatelya k dvizhku tsikla myshleniya.
Vazhna predskazuemost: fiksirovannye route i parametry, bez pobochnykh effektov v samom routere.
# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.thinking.loop_full import start as loop_start, stop as loop_stop, status as loop_status, tick_once as loop_tick
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("agent_loop_routes", __name__, url_prefix="/agent/loop")

@bp.route("/start", methods=["POST"])
def start():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(loop_start(
        str(d.get("goal","")),
        int(d.get("interval_sec",5)),
        int(d.get("max_steps",50)),
        int(d.get("max_run_sec",120)),
        int(d.get("idle_break_sec",20))
    ))

@bp.route("/stop", methods=["POST"])
def stop():
    return jsonify(loop_stop())

@bp.route("/tick", methods=["POST"])
def tick():
    return jsonify(loop_tick())

@bp.route("/status", methods=["GET"])
def status():
    return jsonify(loop_status())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_agent_loop.html")

def register(app):
    app.register_blueprint(bp)