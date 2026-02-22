# modules/rag/rag_status_routes_alias.py
from __future__ import annotations
from flask import Flask

# V etom module uzhe obyavlen blyuprint so statusom
from modules.rag.rag_status_http import rag_status_bp
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def register(app: "Flask") -> None:
    """
    Avtoloader dernet register(app), i endpoint /ester/rag/docs/status
    poyavitsya (blyuprint zaregistriruetsya v Flask).
    """
    app.register_blueprint(rag_status_bp)