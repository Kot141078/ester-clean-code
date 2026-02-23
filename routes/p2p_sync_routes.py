# -*- coding: utf-8 -*-
"""
routes/p2p_sync_routes.py - REST/UI dlya P2P Knowledge Sync (CRDT LWW + Merkle).

Mosty:
- Yavnyy: (UI ↔ Sync) - summari, pull/push, yavnyy merge.
- Skrytyy 1: (Doverie/Affekt ↔ Prioritet) - v B-slote sdvig ts dlya vysokodoverennykh lokalnykh elementov.
- Skrytyy 2: (Ontologiya/KG ↔ Normalizatsiya) - normalizuem tekst pri merzhe dlya soglasovannosti.

Zemnoy abzats:
Dve knopki - «vytyanut» i «zalit». Esli korni sovpali - nichego delat ne nado.
Esli net - gonyaem tolko otlichiya, bez tyazhelykh baz.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template
from modules.p2p.knowledge_sync import summary, pull_since, push_bundle, merge_items
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("p2p_sync_routes", __name__, url_prefix="/p2p_sync")

@bp.get("/probe")
def probe():
    return jsonify({"ok": True})

@bp.get("/summary")
def sum_():
    return jsonify(summary())

@bp.post("/pull")
def pull():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(pull_since(str(d.get("root","") or ""), int(d.get("max_items", 200))))

@bp.post("/push")
def push():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(push_bundle(d))

@bp.post("/merge")
def merge():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(merge_items(list(d.get("items") or []), author=d.get("author")))

@bp.get("/admin")
def admin():
    return render_template("admin_p2p_sync.html")

def register(app):
    app.register_blueprint(bp)

# finalnaya stroka
# c=a+b