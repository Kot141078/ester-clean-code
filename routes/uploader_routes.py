# -*- coding: utf-8 -*-
"""routes/uploader_routes.py - REST: /uploader/prepare

Mosty:
- Yavnyy: (Veb ↔ Ploschadki) gotovim metadannye pod zadannuyu platformu.
- Skrytyy #1: (Portfolio ↔ Ssylki) khorosho stykuetsya s portfolio i outreach.
- Skrytyy #2: (Passport ↔ Trassirovka) fiksiruem vybor shablona.

Zemnoy abzats:
Parametry pod ploschadku - za doli sekundy, bez ruchnoy rutiny.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("uploader_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.uploader.hooks import prepare as _prep  # type: ignore
except Exception:
    _prep=None  # type: ignore

@bp.route("/uploader/prepare", methods=["POST"])
def api_prepare():
    if _prep is None: return jsonify({"ok": False, "error":"uploader_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_prep(str(d.get("script","")), str(d.get("platform","youtube"))))
# c=a+b