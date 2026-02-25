# -*- coding: utf-8 -*-
"""routes/context_routes.py - ruchki dlya proverki adapterov.

Primery:
  POST /context/test/web {"text":"Privet!"}
  POST /context/test/file {"filename":"demo.txt","summary":"Kratkiy otchet"}
  POST /context/test/thought {"goal":"nayti reshenie","conclusion":"gotovo"}

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.context import web_adapter, files_adapter, thoughts_adapter
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("context_routes", __name__, url_prefix="/context/test")

@bp.route("/web", methods=["POST"])
def web_test():
    d=request.get_json(force=True,silent=True) or {}
    web_adapter.record_user_message(d.get("text",""))
    return jsonify({"ok":True})

@bp.route("/file", methods=["POST"])
def file_test():
    d=request.get_json(force=True,silent=True) or {}
    files_adapter.record_file_read(d.get("filename","unknown"),d.get("summary",""))
    return jsonify({"ok":True})

@bp.route("/thought", methods=["POST"])
def thought_test():
    d=request.get_json(force=True,silent=True) or {}
    thoughts_adapter.record_thought(d.get("goal",""),d.get("conclusion",""))
    return jsonify({"ok":True})

def register(app):
    app.register_blueprint(bp)