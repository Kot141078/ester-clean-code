# -*- coding: utf-8 -*-
"""routes/rag_routes.py - REST: /rag/hybrid/search

Mosty:
- Yavnyy: (Veb ↔ Poisk) ustoychivyy gibridnyy retriver dostupen kak ruchka.
- Skrytyy #1: (Profile ↔ Prozrachnost) log zaprosov.
- Skrytyy #2: (Volya ↔ Mysli) ekshen dlya thinking_pipeline.

Zemnoy abzats:
Odin POST - i poluchaem spisok relevantnykh kusochkov dazhe bez vektornoy BD; esli vektora est - stanovitsya esche luchshe.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("rag_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.rag.hybrid import hybrid_search as _hyb  # type: ignore
except Exception:
    _hyb=None  # type: ignore

@bp.route("/rag/hybrid/search", methods=["POST"])
def api_search():
    if _hyb is None: return jsonify({"ok": False, "error":"rag_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_hyb(str(d.get("q","")), int(d.get("top_k",0)) or None))
# c=a+b