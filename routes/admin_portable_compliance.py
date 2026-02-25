# routes/admin_portable_compliance.py
# -*- coding: utf-8 -*-
"""routes/admin_portable_compliance.py - administrativnye endpointy sootvetstviya/komplaensa portable-sborok.

Mosty:
- Yavnyy (Portable ↔ Compliance): esli enterprise-modul est - podklyuchaem ego UI/API pod /admin/portable/compliance.
- Skrytyy #1 (Ekspluatatsiya ↔ Bezopasnost): otsutstvie modulya ne vyzyvaet ImportError na starte.
- Skrytyy #2 (Nablyudaemost ↔ Dokumentooborot): dazhe bez modulya otdaem “stub”-status, chtoby panel ne padala.

Zemnoy abzats:
Role fayla - myagko podklyuchit blyuprint iz modules.portable.compliance (ili sovmestimogo paketa).
Pri otsutstvii - zaregistrirovat nebolshoy stub-rout, chtoby UI can ask status.
# c=a+b"""
from __future__ import annotations

import logging
from typing import Dict
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_portable_compliance_stub", __name__)

@bp.get("/admin/portable/compliance/status")
def portable_compliance_stub():
    return jsonify({"ok": False, "checks": [], "error": "modules.portable.compliance_unavailable"})

def _safe_register(app, bp, prefix: str):
    try:
        app.register_blueprint(bp, url_prefix=prefix)
        logging.info("Admin Portable Complianke: connected ZZF0Z", prefix)
    except Exception as e:
        logging.error("Admin Portable Complianke: failed to connect ZZF0Z: ZZF1ZZ", prefix, e)

def register_routes(app, seen_endpoints: Dict[str, str] | None = None):
    # 1) Trying to connect a ready-made blueprint
    try:
        from modules.portable.compliance import bp as compliance_bp  # type: ignore
        _safe_register(app, compliance_bp, "/admin/portable/compliance")
        return
    except Exception as e:
        logging.warning("Portable Compliance: modules.portable.compliance.bp nedostupen: %s", e)

    # 2) Trying through the factory
    try:
        m = __import__("modules.portable.compliance", fromlist=["get_admin_blueprint"])
        if hasattr(m, "get_admin_blueprint"):
            compliance_bp = m.get_admin_blueprint()  # type: ignore
            _safe_register(app, compliance_bp, "/admin/portable/compliance")
            return
    except Exception as e:
        logging.warning("Portable Compliance: get_admin_blueprint nedostupen: %s", e)

    # 3) Status-zaglushka
    _safe_register(app, bp, "")


def register(app):
    app.register_blueprint(bp)
    return app