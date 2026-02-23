# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from modules import net_manager
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("net_fetch", __name__)

@bp.route("/net/search", methods=["POST"])
def net_search():
    """Endpoint for manual search request."""
    data = request.json
    query = data.get("q")
    if not query:
        return jsonify({"ok": False, "error": "No query"}), 400
        
    res = net_manager.search_internet(query)
    return jsonify(res)