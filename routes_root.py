# -*- coding: utf-8 -*-
"""
Kornevye marshruty (Root Routes):
- GET /           -> UI ili Redirect
- GET /health     -> Health Check
- GET /openapi.json -> API Schema
"""
import os
import json
from flask import Blueprint, jsonify, redirect, send_from_directory
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Sozdaem Blueprint
bp = Blueprint('routes_root', __name__)

@bp.route('/')
def index():
    """Glavnaya tochka vkhoda."""
    # Esli est UI (static/index.html), otdaem ego
    if os.path.exists("static/index.html"):
        return send_from_directory("static", "index.html")
    # Inache redirekt na dokumentatsiyu
    return redirect("/docs")

@bp.route('/health')
def health():
    """Proverka zdorovya dlya Docker/Monitor."""
    return jsonify({
        "status": "ok", 
        "mode": os.getenv("ESTER_MODE", "judge"),
        "hardware": os.getenv("ESTER_HARDWARE", "unknown")
    })

@bp.route('/favicon.ico')
def favicon():
    """Zaglushka dlya ikonki."""
    return "", 204

@bp.route('/openapi.json')
def openapi():
    """Otdacha OpenAPI spetsifikatsii."""
    path = os.getenv("OPENAPI_PATH", "openapi.yaml")
    
    if os.path.exists(path):
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                return jsonify(yaml.safe_load(f))
        except ImportError:
            pass 
        except Exception:
            pass

    # Folbek
    return jsonify({
        "openapi": "3.0.0",
        "info": {"title": "Ester API", "version": "2.0"},
        "paths": {}
    })

@bp.route('/build')
def build():
    """Informatsiya o sborke."""
    return jsonify({
        "name": "Ester",
        "build_date": os.getenv("BUILD_DATE", "dev"),
        "persist_dir": os.getenv("PERSIST_DIR", "./memory"),
        "collection": os.getenv("COLLECTION_NAME", "ester_memory"),
        "mode": os.getenv("DEFAULT_MODE", "judge"),
    })