# -*- coding: utf-8 -*-
"""routes/task_tutor_routes.py - REST/UI dlya TaskTutor.

Ruchki:
  GET /tutor/list
  POST /tutor/create {"title":"...","intent":"..."}
  GET /tutor/get?id=scn_x
  POST /tutor/save {scenario: {...}}
  POST /tutor/validate {"id":"scn_x"}
  POST /tutor/play {"id":"scn_x","mode":"A|B"}
  POST /tutor/remove {"id":"scn_x"}
  POST /tutor/append_step {"id":"scn_x","step":{...}}
  POST /tutor/insert_step {"id":"scn_x","idx":0,"step":{...}}
  POST /tutor/delete_step {"id":"scn_x","idx":0}

  GET /admin/task_tutor

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.agents import task_tutor as TT
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("task_tutor_routes", __name__, url_prefix="/tutor")

@bp.route("/list", methods=["GET"])
def list_():
    return jsonify(TT.list_())

@bp.route("/create", methods=["POST"])
def create():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(TT.create_from_intent(d.get("title",""), d.get("intent","")))

@bp.route("/get", methods=["GET"])
def get():
    sid=request.args.get("id","")
    return jsonify(TT.get(sid))

@bp.route("/save", methods=["POST"])
def save():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(TT.save(d.get("scenario") or {}))

@bp.route("/validate", methods=["POST"])
def validate():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(TT.validate(d.get("id","")))

@bp.route("/play", methods=["POST"])
def play():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(TT.play(d.get("id",""), d.get("mode")))

@bp.route("/remove", methods=["POST"])
def remove():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(TT.remove(d.get("id","")))

@bp.route("/append_step", methods=["POST"])
def append_step():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(TT.append_step(d.get("id",""), d.get("step") or {}))

@bp.route("/insert_step", methods=["POST"])
def insert_step():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(TT.insert_step(d.get("id",""), int(d.get("idx",0)), d.get("step") or {}))

@bp.route("/delete_step", methods=["POST"])
def delete_step():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(TT.delete_step(d.get("id",""), int(d.get("idx",0))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_task_tutor.html")

def register(app):
    app.register_blueprint(bp)