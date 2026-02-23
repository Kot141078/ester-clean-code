# -*- coding: utf-8 -*-
"""
routes/mem_entity_linker_routes.py — HTTP-ruchka avto-linkovki suschnostey dlya pamyati/gipotez.

Endpointy:
  • POST /mem/entity/link {"text":"...", "upsert":true} v†' {"entities":[...], "upsert":{...}}

Mosty:
- Yavnyy: (KG v†" Memory) svyazyvaem tekst zapisey s uzlami grafa.
- Skrytyy #1: (Infoteoriya v†" Poisk) uvelichenie pokrytii suschnostyami — luchshe yakorya dlya RAG.
- Skrytyy #2: (Inzheneriya v†" Ustoychivost) chistyy fallback bez vneshnikh zavisimostey.

Zemnoy abzats:
Eto knopka «raspoznat i svyazat»: bystro proshtampovat imena/mesta v tekste zapisi.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_mem_link = Blueprint("mem_entity_link", __name__)

try:
    from modules.nlp.entity_linker import link_text  # type: ignore
except Exception:
    link_text = None  # type: ignore

def register(app):
    app.register_blueprint(bp_mem_link)

@bp_mem_link.route("/mem/entity/link", methods=["POST"])
def api_link():
    if link_text is None:
        return jsonify({"ok": False, "error": "entity linker unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    upsert = bool(data.get("upsert", True))
    if not text:
        return jsonify({"ok": False, "error": "text required"}), 400
# return jsonify(link_text(text, upsert=upsert))