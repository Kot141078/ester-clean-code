# -*- coding: utf-8 -*-
from __future__ import annotations
"""
routes/debug_echo_routes.py — dev-echo dlya proverki kodirovki vkhoda.

Ruchki:
  • POST /_debug/echo → vozvraschaet {"raw_len": int, "json": any|None, "charset": str|None}

MOSTY:
- Yavnyy: Klient ↔ Server (vidim, chto realno prishlo na server).
- Skrytyy #1: Kodirovka ↔ Parser (charset iz request.mimetype_params).
- Skrytyy #2: Diagnostika ↔ RAG (mozhno bystro ponyat, pochemu poisk pustoy).

ZEMNOY ABZATs:
Diagnosticheskaya ruchka, bez zavisimostey. Ne ostavlyat vklyuchennoy v prode.
# c=a+b
"""
from flask import Blueprint, request, jsonify
import json as _json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("debug_echo_bp", __name__)

@bp.post("/_debug/echo")
def echo():
    raw = request.get_data(cache=False, as_text=False)
    charset = request.mimetype_params.get("charset") if request.mimetype_params else None
    try:
        js = request.get_json(silent=True)
    except Exception:
        js = None
    return jsonify({
        "raw_len": len(raw),
        "json": js,
        "charset": charset
    }), 200

def register(app):
    app.register_blueprint(bp)

__all__ = ["bp","register"]
# c=a+b