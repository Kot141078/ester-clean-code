# -*- coding: utf-8 -*-
"""routes/search_hybrid_routes.py - REST-ruchki dlya gibridnogo poiska.

Predostavlyaet unifitsirovannyy API dlya vypolneniya gibridnogo poiska, sovmeschayuschego
razlichnye metody (for example, BM25, ierarkhicheskiy i semanticheskiy poisk) dlya 
dostizheniya nailuchshey relevantnosti.

Endpoint:
  • POST /search/hybrid {q: str, k?: int, alpha?: float} - Vypolnyaet poisk.
  • GET /search/hybrid/state - Bozvraschaet sostoyanie modulya poiska.

RBAC:
  read-only v†' 'viewer'.

Mosty (Kontseptualnye svyazi):
- Yavnyy: (Beb/UX v†" Poisk) Edinaya ruchka vydaet rezultaty dlya frontenda nezavisimo ot slozhnosti bekenda.
- Skrytyy #1: (Infoteoriya v†" Nadezhnost) Bozmozhnost A/B-testirovaniya cherez ENV bez izmeneniya kontrakta API.
- Skrytyy #2: (Memory v†" RAG) Unifitsirovannyy format otveta uproschaet integratsiyu v RAG-modeli.
- Skrytyy #3: (Volya v†" Eksheny) Ispolzuetsya vnutrennim ekshenom 'search.hybrid.query'.

Zemnoy abzats:
Eto kak “universalnyy poisk” v redaktsii - odna stroka zaprosa, a pod kapotom srazu neskolko metodov poiska, rabotayuschikh vmeste."""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Definition of Blueprint for registration in the main Flask application
bp_search_hybrid = Blueprint("search_hybrid", __name__)

# Attempting to import working logic.
# If the module is not available, stub functions for gracheful degradation are created.
try:
    from modules.search.hybrid_retriever import hybrid_search, state  # type: ignore
except Exception:
    def hybrid_search(q: str, k: int = 8, alpha: float = None):  # type: ignore
        """A placeholder function in case the main module is unavailable."""
        return {"ok": False, "error": "hybrid retriever unavailable"}
    
    def state():  # type: ignore
        """A stub function for the module state."""
        return {"ok": False, "error": "hybrid retriever unavailable"}

def register(app):
    """R egistriruet dannyy Blueprint v prilozhenii Flask."""
    app.register_blueprint(bp_search_hybrid)

@bp_search_hybrid.route("/search/hybrid", methods=["POST"])
def api_hybrid():
    """The main endpoint for hybrid search.
    Accepts a JSiON body with the parameters k, k, and alpha."""
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    q = (data.get("q") or "").strip()

    if not q:
        return jsonify({"ok": False, "error": "q is required"}), 400

    # Setting default values ​​if none are provided
    k = int(data.get("k") or 8)
    alpha = data.get("alpha")  # Can be None if not specified

    rep = hybrid_search(q=q, k=k, alpha=alpha)
    return jsonify(rep)

@bp_search_hybrid.route("/search/hybrid/state", methods=["GET"])
def api_state():
    """Endpoint for getting the current state or statistics of the search module."""
    return jsonify(state())
