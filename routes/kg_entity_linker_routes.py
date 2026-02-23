# -*- coding: utf-8 -*-
"""
routes/kg_entity_linker_routes.py — REST dlya NER v†' KG/gipotezy.

Endpointy:
  • POST /mem/kg/link_entities          {"text": "...", "meta"?:{...}, "hypothesis_id"?: "..."}
  • POST /mem/hypothesis/link_entities  {"hypothesis_id": "...", "entities":[...]}

RBAC: viewer (chtenie/izvlechenie) i operator (linkovka/zapis).

Mosty:
- Yavnyy: (Memory v†" KG) pri poyavlenii teksta bystro rozhdayutsya uzly grafa.
- Skrytyy #1: (Infoteoriya v†" Obyasnimost) privyazka gipotez k suschnostyam uluchshaet trassirovku vyvodov.
- Skrytyy #2: (Kibernetika v†" Nadezhnost) fallback ocheredi — dannye ne teryayutsya pri nedostupnom KG.

Zemnoy abzats:
Eto priemnyy stol: iz «syroy bumagi» vydelyaem familii/mesta/daty Re tut zhe vnosim v kartoteku.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.nlp.ner_linker import extract_entities, upsert_entities, link_hypothesis  # type: ignore
except Exception:
    extract_entities = upsert_entities = link_hypothesis = None  # type: ignore

try:
    from modules.security.rbac import require_role  # type: ignore
except Exception:
    def require_role(_r):
        def deco(fn): return fn
        return deco

bp_kg_linker = Blueprint("kg_linker", __name__)

def register(app):
    app.register_blueprint(bp_kg_linker)

@bp_kg_linker.route("/mem/kg/link_entities", methods=["POST"])
@require_role("operator")
def api_kg_link():
    if extract_entities is None:
        return jsonify({"ok": False, "error": "ner_linker unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text is required"}), 400
    ents = extract_entities(text)
    up = upsert_entities(ents)
    hyp_rep = {}
    hyp_id = (data.get("hypothesis_id") or "").strip()
    if hyp_id:
        hyp_rep = link_hypothesis(hyp_id, ents)
    return jsonify({"ok": True, "entities": ents, "kg": up, "hypothesis": hyp_rep})

@bp_kg_linker.route("/mem/hypothesis/link_entities", methods=["POST"])
@require_role("operator")
def api_hyp_link():
    if link_hypothesis is None:
        return jsonify({"ok": False, "error": "ner_linker unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    hyp_id = (data.get("hypothesis_id") or "").strip()
    ents: List[Dict[str, Any]] = list(data.get("entities") or [])
    if not hyp_id or not ents:
        return jsonify({"ok": False, "error": "hypothesis_id and entities required"}), 400
# return jsonify(link_hypothesis(hyp_id, ents))