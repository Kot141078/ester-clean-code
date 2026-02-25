# routes/admin_portable.py
# -*- coding: utf-8 -*-
"""routes/admin_portable.py - administrative endpointy Portable (myagkaya registratsiya).

Mosty:
- Yavnyy (Portable ↔ UI admina): podklyuchaem panel portable-sborok pod /admin/portable, esli enterprise-moduli est.
- Skrytyy #1 (Bezopasnost ↔ Ekspluatatsiya): ImportError ne valit prilozhenie - prosto pokazyvaem stub-status.
- Skrytyy #2 (Nablyudaemost ↔ Dokumentooborot): otdaem svodnyy JSON o dostupnosti portable-componentov.

Zemnoy abzats:
Fayl ne realizuet zapis fleshek sam. On akkuratno podklyuchaet blyuprinty iz modules.portable.*. Esli packageov net,
registratsiya propuskaetsya, a bazovye /admin/portable/status ostayutsya dostupny dlya UI.
# c=a+b"""
from __future__ import annotations

import logging
from typing import Dict, Any
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_portable_stub", __name__)

@bp.get("/admin/portable/status")
def portable_status():
    return jsonify({
        "ok": False,
        "error": "modules.portable_unavailable",
        "components": {"usb": False, "compliance": False, "image": False}
    })

def _safe_register(app, bp, prefix: str):
    try:
        app.register_blueprint(bp, url_prefix=prefix)
        logging.info("Admin Portable: ZZF0Z connected", prefix)
    except Exception as e:
        logging.error("Admin Portable: failed to connect ZZF0Z: ZZF1ZZ", prefix, e)

def register_routes(app, seen_endpoints: Dict[str, str] | None = None):
    # 1) Direct blueprints, if implemented in enterprise packages
    ok = False
    try:
        from modules.portable.admin import bp as adm_bp  # type: ignore
        _safe_register(app, adm_bp, "/admin/portable")
        ok = True
    except Exception as e:
        logging.warning("Admin Portable: modules.portable.admin.bp nedostupen: %s", e)

    try:
        m = __import__("modules.portable", fromlist=["get_admin_blueprint"])
        if hasattr(m, "get_admin_blueprint"):
            adm_bp2 = m.get_admin_blueprint()  # type: ignore
            _safe_register(app, adm_bp2, "/admin/portable")
            ok = True
    except Exception as e:
        logging.warning("Admin Portable: get_admin_blueprint nedostupen: %s", e)

    # 2) If nothing is connected, Steve registers
    if not ok:
        _safe_register(app, bp, "")


def register(app):
    app.register_blueprint(bp)
    return app