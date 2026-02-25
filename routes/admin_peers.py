# routes/admin_peers.py
# -*- coding: utf-8 -*-
"""routes/admin_peers.py - administrative endpointy dlya spiska/statusa pirov (myagkaya registratsiya).

Mosty:
- Yavnyy (P2P ↔ UI admina): panel prosmotra pirov, esli enterprise-modul dostupen.
- Skrytyy #1 (Bezopasnost ↔ Ekspluatatsiya): ImportError ne ronyaet server - pishem preduprezhdenie i idem dalshe.
- Skrytyy #2 (Nablyudaemost ↔ Ustoychivost): otdaem “zaglushku sostoyaniya”, chtoby UI ne padal dazhe bez pirov.

Zemnoy abzats:
Fayl ne realizuet P2P sam, a lish podklyuchaet blyuprinty/khendlery iz modules.p2p.peers pri nalichii.
Esli modul otsutstvuet - registratsiya propuskaetsya, no bazovyy JSON-status dostupen.
# c=a+b"""
from __future__ import annotations

import logging
from typing import Dict, Any
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_peers_stub", __name__)

@bp.get("/admin/peers/status")
def peers_stub_status():
    # Minimum status so that there is no 404 in the UI
    return jsonify({"ok": False, "peers": [], "error": "modules.p2p.peers_unavailable"})

def _safe_register(app, bp, prefix: str):
    try:
        app.register_blueprint(bp, url_prefix=prefix)
        logging.info("Admin-Piers: connected ZZF0Z", prefix)
    except Exception as e:
        logging.error("Admin-Piers: failed to connect ZZF0Z: ZZF1ZZ", prefix, e)

def register_routes(app, seen_endpoints: Dict[str, str] | None = None):
    # 1) Direct blueprint bp
    try:
        from modules.p2p.peers import bp as peers_bp  # type: ignore
        _safe_register(app, peers_bp, "/admin/peers")
        return
    except Exception as e:
        logging.warning("Admin-Peers: modules.p2p.peers.bp nedostupen: %s", e)

    # 2) Fabrika blyuprinta
    try:
        m = __import__("modules.p2p.peers", fromlist=["get_admin_blueprint"])
        if hasattr(m, "get_admin_blueprint"):
            peers_bp = m.get_admin_blueprint()  # type: ignore
            _safe_register(app, peers_bp, "/admin/peers")
            return
    except Exception as e:
        logging.warning("Admin-Peers: get_admin_blueprint nedostupen: %s", e)

    # 3) Stab: registriruem minimalnyy status pod /admin/peers/status
    _safe_register(app, bp, "")  # bez prefiksa - v fayle uzhe propisan put


def register(app):
    app.register_blueprint(bp)
    return app