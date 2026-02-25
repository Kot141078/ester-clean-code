# -*- coding: utf-8 -*-
"""routes/memory_graph_routes.py - REST/UI dlya grafa pamyati.

Ruchki:
  GET /memory_graph/data
  GET /memory_graph/search?q=...
  GET /admin/memory_graph

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.memory.graph import build_graph, filter_graph
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("memory_graph_routes", __name__, url_prefix="/memory_graph")

@bp.route("/data", methods=["GET"])
def data():
    return jsonify(build_graph())

@bp.route("/search", methods=["GET"])
def search():
    q = request.args.get("q","")
    return jsonify(filter_graph(q))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_memory_graph.html")

def register(app):
    app.register_blueprint(bp)