# -*- coding: utf-8 -*-
from __future__ import annotations
import os, base64
from flask import Blueprint, current_app, send_from_directory, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_bp = Blueprint("favicon_routes_alias", __name__)
_AB = os.getenv("ESTER_FAVICON_AB", "B").upper()  # B=on by default

_MIN_ICO_B64 = (
    "AAABAAEAEBAAAAEAIABoAwAAFgAAACgAAAAQAAAAIAAAAAEAGAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)

@_bp.route("/favicon.ico")
def _favicon():
    try:
        static_dir = current_app.static_folder or os.path.join(os.getcwd(), "static")
        cand = os.path.join(static_dir, "favicon.ico")
        if os.path.isfile(cand):
            return send_from_directory(static_dir, "favicon.ico", mimetype="image/x-icon")
    except Exception:
        pass
    data = base64.b64decode(_MIN_ICO_B64)
    return Response(data, mimetype="image/x-icon")

def register(app):
    if _AB == "B":
        app.register_blueprint(_bp)
# c=a+b