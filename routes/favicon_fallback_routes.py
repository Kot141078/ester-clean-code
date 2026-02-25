# -*- coding: utf-8 -*-
"""routes/favicon_fallback_routes.py - ispravlyaet 500 na /favicon.ico.

MOSTY:
- Yavnyy: (Brauzer ↔ UI) vsegda otdaet validnyy favicon, dazhe esli staticheskie fayly ne nastroeny.
- Skrytyy #1: (AB-slot ↔ Otkat) ESTER_FAVICON_FALLBACK_AB (A|B), po umolchaniyu VKL (B).
- Skrytyy #2: (Logi ↔ Diagnostika) pishet v log pri first obraschenii.

ZEMNOY ABZATs:
Brauzery pochti vsegda zaprashivayut /favicon.ico - vmesto 500 vernem malenkuyu PNG-ikonku, chtoby stranitsa gruzilas bez krasnykh oshibok.

c=a+b"""
from __future__ import annotations
import os, base64, logging
from flask import Blueprint, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("favicon_fallback", __name__)

_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="

def _ab_enabled() -> bool:
    return (os.getenv("ESTER_FAVICON_FALLBACK_AB", "B") or "B").upper() == "B"

@bp.get("/favicon.ico")
def favicon():
    if not _ab_enabled():
        return Response(status=204)
    try:
        raw = base64.b64decode(_PNG_B64)
        return Response(raw, mimetype="image/png")
    except Exception as e:
        logging.exception("favicon fallback failed: %s", e)
        return Response(status=204)

def register(app):
    app.register_blueprint(bp)
# c=a+b