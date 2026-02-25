# -*- coding: utf-8 -*-
"""Drop-in alias that serves favicon robustly, without depending on anything else.
Endpoints:
  GET /_alias2/favicon.ico
  GET /_alias2/favicon/ping -> {"ok": true}

AB flag: ESTER_FAVICON_ALIAS2_AB (A|B), default B = enabled

Mosty:
- Yavnyy: Flask Blueprint -> staticheskaya razdacha favicon (static/favicon.ico ili vstroennyy baytovyy fallback).
- Skrytyy #1: (Reloader/dvoynoy import ↔ Registratsiya) - zaschita ot povtornoy registratsii BP s tem zhe imenem.
- Skrytyy #2: (Logi ↔ Nablyudaemost) - myagkiy log cherez app.logger pri skip registratsii.

Zemnoy abzats:
Fayl otvechaet za odnu vesch: garantirovannuyu otdachu favicon bez 500-ok. Main problem byla v
povtornoy registratsii blueprint s odinakovym imenem pri goryachem reloade/dvoynom importe. Corrected
akkuratno: pered app.register_blueprint my proveryaem app.blueprints i, esli imya zanyato, prosto vykhodim.
Naruzhnye route ne menyalis.
# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, current_app, send_from_directory, Response, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Blueprint name fixed for route compatibility
_BP_NAME = "favicon_alias2"
_bp = Blueprint(_BP_NAME, __name__)

_AB = os.getenv("ESTER_FAVICON_ALIAS2_AB", "B").upper() or "B"

# A tiny 1×1 ICO (fallback) - valid minimal Windows icon (favicon).
_FALLBACK_ICO = (
    b"\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x01\x00\x18\x00"
    b"\x16\x00\x00\x00\x22\x00\x00\x00\x00\x00\x00\x00\x28\x00"
    b"\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x18\x00"
    b"\x00\x00\x00\x00\x02\x00\x00\x00\x13\x0B\x00\x00\x13\x0B"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF\xFF\x00"
)

def _try_static_favicon():
    try:
        static_folder = current_app.static_folder or "static"
        cand = os.path.join(static_folder, "favicon.ico")
        if os.path.isfile(cand):
            return send_from_directory(static_folder, "favicon.ico")
    except Exception:
        pass
    # Fallback: tiny in-memory icon (never 500)
    return Response(_FALLBACK_ICO, mimetype="image/x-icon")

@_bp.get("/_alias2/favicon.ico")
def _favicon():
    return _try_static_favicon()

@_bp.get("/_alias2/favicon/ping")
def _ping():
    return jsonify(ok=True, ab=_AB, bp=_BP_NAME)

def register(app):
    """Secure registration of BP with protection against re-addition under the same name."""
    if _AB != "B":
        return
    # If there is already a power supply with the same name, do not register it a second time
    existing = app.blueprints.get(_BP_NAME)
    if existing is not None:
        try:
            if hasattr(app, "logger"):
                app.logger.debug("[favicon_alias2] blueprint already registered, skipping")
        finally:
            return
    app.register_blueprint(_bp)
