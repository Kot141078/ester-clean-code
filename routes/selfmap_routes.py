# -*- coding: utf-8 -*-
"""routes/selfmap_routes.py - REST: /self/map

Mosty:
- Yavnyy: (Veb ↔ Samokarta) JSON-portret sposobnostey.
- Skrytyy #1: (Profile ↔ Prozrachnost) snimok fiksiruetsya.
- Skrytyy #2: (UI ↔ Dashbord) ispolzuetsya dashbordom.

Zemnoy abzats:
Odin GET - i my znaem, chto podklyucheno, kakie eksheny dostupny i kakie flagi sredy vklyucheny.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("selfmap_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.selfmap.introspect import snapshot as _snap  # type: ignore
except Exception:
    _snap=None  # type: ignore

@bp.route("/self/map", methods=["GET"])
def api_map():
    if _snap is None: return jsonify({"ok": False, "error":"selfmap_unavailable"}), 500
    return jsonify(_snap())
# c=a+b