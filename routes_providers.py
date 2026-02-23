# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def register_providers_routes(app, providers, url_prefix: str = "/providers"):
    bp = Blueprint("providers", __name__)

    @bp.get(url_prefix + "/status")
    @jwt_required()
    def providers_status():
        return jsonify(providers.status())

    @bp.post(url_prefix + "/select")
    @jwt_required()
    def providers_select():
        data = request.get_json(force=True, silent=True) or {}
        mode = str(data.get("mode") or "")
        try:
            res = providers.select(mode)
            return jsonify(res)
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @bp.get(url_prefix + "/models")
    @jwt_required()
    def providers_models():
        try:
            return jsonify({"items": providers.models()})
        except Exception:
            return jsonify({"items": []})

# app.register_blueprint(bp)