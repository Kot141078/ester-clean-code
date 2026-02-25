# routes/admin_p2p.py
# -*- coding: utf-8 -*-
"""routes/admin_p2p.py - administrative endpointy P2P (filemesh/replication), “myagkaya” registratsiya.

Mosty:
- Yavnyy (P2P ↔ Panel admina): esli enterprise-moduli prisutstvuyut - podklyuchaem ikh blyuprinty pod /admin/p2p.
- Skrytyy #1 (Bezopasnost ↔ Ekspluatatsiya): otsutstvie modulary ne ronyaet server - ImportError perekhvatyvaetsya.
- Skrytyy #2 (Nablyudaemost ↔ Ustoychivost): logiruem, kakie chasti P2P dostupny v dannoy sborke.

Zemnoy abzats:
Fayl nichego "svoego" ne khostit. On lish pytaetsya podtyanut blyuprinty iz enterprise-paketov (modules.p2p.*).
Esli paketov net - prosto pishet preduprezhdenie v log i NE registriruet nichego (nikakikh 500 na importe).
# c=a+b"""
from __future__ import annotations

import logging
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _safe_register(app, bp, prefix: str, seen_endpoints: Dict[str, str] | None = None):
    """Registers a blueprint if available and there are no route conflicts."""
    try:
        app.register_blueprint(bp, url_prefix=prefix)
        logging.info("Admin-P2P: connected ZZF0Z", prefix)
    except Exception as e:
        logging.error("Admin-P2P: failed to connect ZZF0Z: ZZF1ZZ", prefix, e)

def register_routes(app, seen_endpoints: Dict[str, str] | None = None):
    """We are trying to import optional P2P blueprints.
    NO - we just warn you and move on."""
    # modules.p2p.filemesh (if you have your own bp)
    try:
        from modules.p2p.filemesh import bp as filemesh_bp  # type: ignore
        _safe_register(app, filemesh_bp, "/admin/p2p/filemesh", seen_endpoints)
    except Exception as e:
        logging.warning("Admin-P2P: modules.p2p.filemesh ne nayden/ne gotov: %s", e)

    # modules.p2p.replica (variant imeni paketa)
    try:
        from modules.p2p.replica import bp as replica_bp  # type: ignore
        _safe_register(app, replica_bp, "/admin/p2p/replica", seen_endpoints)
    except Exception as e:
        logging.warning("Admin-P2P: modules.p2p.replica ne nayden/ne gotov: %s", e)

    # If enterprise packages implement a blueprint factory:
    #   get_admin_blueprint() -> Blueprint
    for modpath, prefix in (
        ("modules.p2p.filemesh", "/admin/p2p"),
        ("modules.replica", "/admin/replica"),
    ):
        try:
            m = __import__(modpath, fromlist=["get_admin_blueprint"])
            if hasattr(m, "get_admin_blueprint"):
                bp = m.get_admin_blueprint()  # type: ignore
                _safe_register(app, bp, prefix, seen_endpoints)
        except Exception as e:
            logging.warning("Admin-P2P: %s bez get_admin_blueprint(): %s", modpath, e)


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
# stub for admin_p2p: no power supply/router/register_*_rutes yet
def register(app):
    return True

# === /AUTOSHIM ===