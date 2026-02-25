# -*- coding: utf-8 -*-
"""/matrix (optime/CNC/RSS/offers/rules, plus meta-memory with update(days=14))."""
import time

import psutil
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

start_time = time.time()


def register_metrics_routes(app, memory_manager, url_prefix="/metrics"):
    bp = Blueprint("metrics", __name__)

    @bp.get(url_prefix)
    @jwt_required()
    def get_metrics():
        info = {
            "uptime_sec": int(time.time() - start_time),
            "cpu_percent": psutil.cpu_percent(),
            "rss_mb": psutil.Process().memory_info().rss / (1024 * 1024),
            "proactivity_metrics": memory_manager.get_proactivity_metrics(),
        }
        meta = memory_manager.update_meta_memory(days=14)
        return jsonify({**info, "meta": meta})

# app.register_blueprint(bp)