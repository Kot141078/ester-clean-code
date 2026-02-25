# -*- coding: utf-8 -*-
"""routes/mem_routes.py - bazovye REST-ruchki pamyati.

MOSTY:
- (Yavnyy) POST /mem/put, GET /mem/get/<id>, GET /mem/search?q=&top_k=
- (Skrytyy #1) Normalizuet zapis (kind/text/meta), layer vybiraetsya avtomaticheski.
- (Skrytyy #2) Bez vneshnikh zavisimostey; khranenie v data/mem/<layer>/*.json

ZEMNOY ABZATs:
This is “okoshko arkhiva”: polozhit kartochku, nayti pokhozhie, dostat po nomeru.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, request, jsonify
from modules.memory.layers import store, get, search
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mem_routes", __name__, url_prefix="/mem")

def register(app):
    app.register_blueprint(bp)

@bp.post("/put")
def mem_put():
    data = request.get_json(silent=True) or {}
    kind = str(data.get("kind","note"))
    text = str(data.get("text","") or "")
    meta = data.get("meta") or {}
    if not text:
        return jsonify({"ok": False, "error": "text required"}), 400
    doc = store(kind, text, meta)
    return jsonify({"ok": True, "doc": doc})

@bp.get("/get/<doc_id>")
def mem_get(doc_id: str):
    doc = get(doc_id)
    if not doc:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "doc": doc})

@bp.get("/search")
def mem_search():
    q = request.args.get("q","").strip()
    top_k = int(request.args.get("top_k","0") or "0") or None
    if not q:
        return jsonify({"ok": False, "error": "q required"}), 400
    items = search(q, top_k=top_k)
    return jsonify({"ok": True, "items": items})
# c=a+b