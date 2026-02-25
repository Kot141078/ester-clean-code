# -*- coding: utf-8 -*-
"""routes/kg_link_routes.py - REST: extract/upsert/stats dlya legkogo KG-linkera.

This modul predostavlyaet API dlya izvlecheniya imenovannykh suschnostey iz teksta,
ikh dobavleniya (upsert) v graf znaniy (KG) i polucheniya statistiki.

Mosty:
- Yavnyy: (Beb v†" KG) odin vyzov dlya izvlecheniya Re sokhraneniya, plyus otdelnye vyzovy dlya kazhdogo shaga.
- Skrytyy #1: (RAG v†" KG) rezultat mozhet idti srazu v gibridnyy poisk.
- Skrytyy #2: (Memory v†" Profile) sha svyazyvaet iskhodnyy tekst s uzlami v grafe.

Zemnoy abzats:
Korotkie i udobnye ruchki, chtoby “privyazat” tekst k grafu znaniy.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# A more descriptive name for Blueprint from the second file.
bp = Blueprint("kg_link_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    # Let's import all three functions with clearer aliases.
    from modules.kg.linker import extract as _extract, upsert_to_kg as _upsert, stats as _stats  # type: ignore
except Exception:
    _extract = _upsert = _stats = None  # type: ignore

@bp.route("/kg/link/entities", methods=["POST"])
def api_link_entities():
    """Extract entities from text and optionally add them to the knowledge graph.
    This is a convenience endpoint combining extract and upsert."""
    if _extract is None or _upsert is None: return jsonify({"ok": False, "error":"kg_unavailable"}), 500
    
    d = request.get_json(True, True) or {}
    text = str(d.get("text", ""))
    hint_lang = d.get("hint_lang")
    sha = str(d.get("sha", "")) # We use ša for consistency.

    # Step 1: Extraction
    rep = _extract(text, hint_lang)
    
    # Step 2: Optional addition to the graph
    if d.get("upsert", True) and rep.get("entities"):
        rep["upsert_result"] = _upsert(rep.get("entities") or {}, sha)
        
    return jsonify(rep)

@bp.route("/kg/link/extract", methods=["POST"])
def api_extract():
    """Only extracts entities from text without saving to a graph."""
    if _extract is None: return jsonify({"ok": False, "error":"kg_unavailable"}), 500
    
    d = request.get_json(True, True) or {}
    text = str(d.get("text", ""))
    hint_lang = d.get("hint_lang") # Gobavlena podderzhka hint_lang iz pervogo fayla.
    
    return jsonify(_extract(text, hint_lang))

@bp.route("/kg/link/upsert", methods=["POST"])
def api_upsert():
    """Takes a dictionary of entities and associates it with the SA in the knowledge graph."""
    if _upsert is None: return jsonify({"ok": False, "error":"kg_unavailable"}), 500
    
    d = request.get_json(True, True) or {}
    entities = d.get("entities") or {}
    sha = str(d.get("sha", ""))
    
    return jsonify(_upsert(entities, sha))

@bp.route("/kg/link/stats", methods=["GET"])
def api_stats():
    """
    Bozvraschaet statistiku po grafu znaniy.
    """
    if _stats is None: return jsonify({"ok": False, "error":"kg_unavailable"}), 500
# return jsonify(_stats())