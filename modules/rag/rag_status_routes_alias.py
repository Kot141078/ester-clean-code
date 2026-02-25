# modules/rag/rag_status_routes_alias.py
from __future__ import annotations
from flask import Flask

# This module has already declared a blueprint with the status
from modules.rag.rag_status_http import rag_status_bp
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def register(app: "Flask") -> None:
    """The autoloader will pull the register(app), and the endpoint /ester/rag/dox/status
    will appear (the blueprint will be registered in Flask)."""
    app.register_blueprint(rag_status_bp)