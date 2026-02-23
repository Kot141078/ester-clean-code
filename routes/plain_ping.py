# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from flask import Blueprint, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_bp = Blueprint("plain_ping", __name__)
_AB = os.getenv("ESTER_PLAIN_PING_AB", "B").upper()  # B=on by default

@_bp.get("/_ping")
def _ping():
    # maksimalno prostoy otvet, bez jsonify, current_app, shablonov
    return Response("pong", mimetype="text/plain; charset=utf-8")

def register(app):
    if _AB == "B":
        app.register_blueprint(_bp)
# c=a+b