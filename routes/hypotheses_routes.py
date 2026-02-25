# -*- coding: utf-8 -*-
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("hypotheses_routes", __name__)

@bp.get("/hypotheses")
def list_hypotheses():
    """Light plug: so that the UI does not fall. Real logic can live in modules."""
    return jsonify({"ok": True, "items": []})

@bp.post("/hypotheses")
def create_hypothesis():
    data = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "stored": data}), 201