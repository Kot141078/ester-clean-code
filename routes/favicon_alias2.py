
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, io
from flask import Blueprint, send_file, make_response, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_AB = os.getenv("ESTER_FAVICON_ALIAS2_AB", "B").upper()
_bp = Blueprint("favicon_alias2", __name__)

SEARCH_PATHS = [
    os.getenv("ESTER_FAVICON_PATH") or "",
    os.path.join("static", "favicon.ico"),
    os.path.join("templates", "favicon.ico"),
    "favicon.ico",
]

@_bp.get("/_alias2/favicon/ping")
def favicon_ping():
    return jsonify(ok=True, ab=_AB)

@_bp.get("/_alias2/favicon.ico")
def favicon_alias():
    for p in SEARCH_PATHS:
        if p and os.path.isfile(p):
            try:
                r = send_file(p, mimetype="image/x-icon", as_attachment=False)
                r.headers["X-Ester-Favicon-Alias2"] = "served"
                return r
            except Exception as e:
                _log("send_file error: %r" % e)
                break
    # We didn’t find anything - we return 204 without errors
    r = make_response("", 204)
    r.headers["X-Ester-Favicon-Alias2"] = "empty"
    return r

def _log(msg):
    try:
        os.makedirs("data", exist_ok=True)
        with io.open("data/bringup_after_chain.log", "a", encoding="utf-8") as f:
            f.write(u"[FaviconAlias2] %s\n" % msg)
    except Exception:
        pass

def register(app):
    if _AB == "B":
        app.register_blueprint(_bp)
