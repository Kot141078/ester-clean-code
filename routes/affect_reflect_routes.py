# -*- coding: utf-8 -*-
"""
routes/affect_reflect_routes.py - REST: korotkaya affekt-refleksiya (vyborka).

Mosty:
- Yavnyy: (Veb ↔ Refleksiya) otdaem top-N dlya dalneyshego obdumyvaniya.
- Skrytyy #1: (Memory ↔ Ves) uchityvaem emotsii v prioritete.
- Skrytyy #2: (Payplayny ↔ Avtonomiya) legko vstraivaetsya v thinking_pipeline.

Zemnoy abzats:
Dostaem samoe «vazhnoe po chuvstvam» - i dumaem nad etim v pervuyu ochered.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_aff = Blueprint("affect_reflection", __name__)

try:
    from modules.memory.affect_reflection import select_for_reflection as _sel  # type: ignore
except Exception:
    _sel = None  # type: ignore

def register(app):
    app.register_blueprint(bp_aff)

@bp_aff.route("/mem/reflect/affect", methods=["POST"])
def api_reflect():
    if _sel is None: return jsonify({"ok": False, "error":"affect reflection unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_sel(int(d.get("k",20)), float(d.get("alpha",1.0))))
# c=a+b