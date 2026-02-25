# -*- coding: utf-8 -*-
"""routes/kg_linker_routes.py - REST: zapustit avto-svyazyvanie KG dlya poslednikh zapisey pamyati.

Mosty:
- Yavnyy: (Veb ↔ KG) odna ruchka dlya paketnoy “skrepki”.
- Skrytyy #1: (RAG ↔ Navigatsiya) kg_keys poyavlyayutsya v meta - imi udobno filtrovat.
- Skrytyy #2: (Hypothezy ↔ Otchetnost) v buduschem syuda prishem /mem/hypothesis/*.

Zemnoy abzats:
Knopka “skrepit”: zapisi pamyati poluchayut ssylki na suschnosti.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_kg_link = Blueprint("kg_linker", __name__)

try:
    from modules.kg.linker import run as _run  # type: ignore
except Exception:
    _run = None  # type: ignore

def register(app):
    # Idempotent registration: if there is already a blueprint (hot reload/double import) - exit.
    if "kg_linker" in app.blueprints:
        try:
            if hasattr(app, "logger"):
                app.logger.debug("[kg_linker] blueprint already registered, skipping")
        finally:
            return
    app.register_blueprint(bp_kg_link)

@bp_kg_link.route("/kg/linker/run", methods=["POST"])
def api_run():
    if _run is None: 
        return jsonify({"ok": False, "error":"kg linker unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_run(int(d.get("limit",50))))
# c=a+b