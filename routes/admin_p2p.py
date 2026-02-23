# routes/admin_p2p.py
# -*- coding: utf-8 -*-
"""
routes/admin_p2p.py - administrativnye endpointy P2P (filemesh/replication), «myagkaya» registratsiya.

Mosty:
- Yavnyy (P2P ↔ Panel admina): esli enterprise-moduli prisutstvuyut - podklyuchaem ikh blyuprinty pod /admin/p2p.
- Skrytyy #1 (Bezopasnost ↔ Ekspluatatsiya): otsutstvie moduley ne ronyaet server - ImportError perekhvatyvaetsya.
- Skrytyy #2 (Nablyudaemost ↔ Ustoychivost): logiruem, kakie chasti P2P dostupny v dannoy sborke.

Zemnoy abzats:
Fayl nichego «svoego» ne khostit. On lish pytaetsya podtyanut blyuprinty iz enterprise-paketov (modules.p2p.*).
Esli paketov net - prosto pishet preduprezhdenie v log i NE registriruet nichego (nikakikh 500 na importe).
# c=a+b
"""
from __future__ import annotations

import logging
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _safe_register(app, bp, prefix: str, seen_endpoints: Dict[str, str] | None = None):
    """Registriruet blyuprint, esli dostupen, i net konfliktov routov."""
    try:
        app.register_blueprint(bp, url_prefix=prefix)
        logging.info("Admin-P2P: podklyuchen %s", prefix)
    except Exception as e:
        logging.error("Admin-P2P: ne udalos podklyuchit %s: %s", prefix, e)

def register_routes(app, seen_endpoints: Dict[str, str] | None = None):
    """
    Pytaemsya importirovat optsionalnye blyuprinty P2P.
    NET - prosto preduprezhdaem i idem dalshe.
    """
    # modules.p2p.filemesh (esli est sobstvennyy bp)
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

    # Esli enterprise-pakety realizuyut fabriku blyuprintov:
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
# zaglushka dlya admin_p2p: poka net bp/router/register_*_routes
def register(app):
    return True

# === /AUTOSHIM ===