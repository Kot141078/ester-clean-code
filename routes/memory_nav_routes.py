# -*- coding: utf-8 -*-
"""
routes/memory_nav_routes.py - REST/UI navigatora pamyati.

Ruchki:
  GET  /mem/probe
  GET  /mem/counts
  GET  /mem/timeline?session=...&scenario=...&limit=300
  GET  /mem/search?q=kind:click_text text:Privet
  POST /mem/quick_demo   # zapisyvaet 3 svyazannykh sobytiya (plan, vospriyatie, deystvie)
  GET  /admin/mem

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.memory import hub as MH
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("memory_nav_routes", __name__, url_prefix="/mem")

@bp.route("/probe", methods=["GET"])
def probe():
    return jsonify({"ok":True,"path":MH.MEM_LOG,"mode":MH.MEM_MODE})

@bp.route("/counts", methods=["GET"])
def counts():
    return jsonify(MH.counts())

@bp.route("/timeline", methods=["GET"])
def timeline():
    session_id = request.args.get("session") or None
    scenario_id = request.args.get("scenario") or None
    limit = int(request.args.get("limit", "300"))
    return jsonify(MH.timeline(session_id, scenario_id, limit))

@bp.route("/search", methods=["GET"])
def search():
    q = request.args.get("q","")
    return jsonify(MH.search(q))

@bp.route("/quick_demo", methods=["POST"])
def quick_demo():
    sess="sess_demo"; scn="scn_demo"
    p=MH.log_plan("desktop","open_app","Otkryt bloknot", session_id=sess, scenario_id=scn, user_id="user:default", step_id="stp_1")
    v=MH.log_perception("vision","ocr_find","Nayden tekst OK",[ ], session_id=sess, scenario_id=scn, user_id="user:default", step_id="stp_2", artifacts={"screenshot":"/tmp/ester_screenshot.png"})
    a=MH.log_action("desktop","click_text","Klik po tekstu OK", {"decision":"allow"}, session_id=sess, scenario_id=scn, user_id="user:default", step_id="stp_3", )
    return jsonify({"ok":True,"ids":[p,v,a]})

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_memory_nav.html")

def register(app):
    app.register_blueprint(bp)