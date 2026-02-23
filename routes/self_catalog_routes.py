# -*- coding: utf-8 -*-
"""
routes/self_catalog_routes.py - REST: /self/catalog i /self/capabilities.

Mosty:
- Yavnyy: (Veb ↔ Samoopis) front/CLI poluchayut polnuyu kartinu vozmozhnostey.
- Skrytyy #1: (Memory ↔ Profile) mozhno dobavit zapis pri zaprosakh.
- Skrytyy #2: (Diagnostika ↔ UX) udobno pri priemke i integratsii moduley.

Zemnoy abzats:
Knopka «kto ya seychas?» - i na ekrane polnaya karta servisov, ekshenov i nastroek.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("self_catalog_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.self.catalog import catalog as _cat, capabilities as _cap  # type: ignore
except Exception:
    _cat=_cap=None  # type: ignore

@bp.route("/self/catalog", methods=["GET"])
def api_catalog():
    if _cat is None: return jsonify({"ok": False, "error":"self_catalog_unavailable"}), 500
    return jsonify(_cat(current_app))

@bp.route("/self/capabilities", methods=["GET"])
def api_capabilities():
    if _cap is None: return jsonify({"ok": False, "error":"self_catalog_unavailable"}), 500
    return jsonify(_cap(current_app))
# c=a+b