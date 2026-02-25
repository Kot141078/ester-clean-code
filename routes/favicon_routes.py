
# -*- coding: utf-8 -*-
"""routes/favicon_routes.py - fiks 500 na /favicon.ico.
Mosty: yavnyy (Brauzer↔Veb); skrytye (UI↔Diagnostika; Bezopasnost↔UX).
Zemnoy abzats: brauzer vsegda dergaet /favicon.ico - otvechaem 1×1 PNG vmesto 500.
c=a+b"""
from __future__ import annotations
from io import BytesIO
from flask import Blueprint, send_file, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("favicon_routes", __name__)

@bp.route("/favicon.ico", methods=["GET"])
def favicon():
    try:
        data_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAn8B9x1x7iAAAAAASUVORK5CYII="
        import base64
        data = BytesIO(base64.b64decode(data_b64))
        data.seek(0)
        return send_file(data, mimetype="image/png", as_attachment=False, download_name="favicon.png")
    except Exception:
        return Response(status=204)

def register(app):
    app.register_blueprint(bp)