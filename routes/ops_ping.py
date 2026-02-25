# -*- coding: utf-8 -*-
"""routes/ops_ping.py — prostye sluzhebnye endpointy operatsionnogo urovnya.

Route:
  • GET /ops/ping - {"ok": true, "node_id": "...", "ts": ...}
  • POST /ops/echo - {"ok": true, "received": <json>}

Mosty:
- Yavnyy (Kibernetika v†" Svyaz): bazovye refleksy “zhiv?” Re "slyshu/povtoryayu".
- Skrytyy 1 (Infoteoriya v†" Nadezhnost): minimum poley v†' maximum primenimosti (LAN test/skleyka).
- Skrytyy 2 (Praktika v†" Vezopasnost): zagolovok X-Ester-Cluster mozhet ispolzovatsya dlya filtratsii (esli nuzhen).

Zemnoy abzats:
Eto “kardiogramma i povtorenie frazy”: proverit, chto uzel zhiv i chto my mozhem dostavit JSON “kak est”.

# c=a+b"""
from __future__ import annotations

import time
import platform
import getpass
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ops_ping = Blueprint("ops_ping", __name__)

def _node_id() -> str:
    return f"{platform.node()}::{getpass.getuser()}"

@bp_ops_ping.get("/ops/ping")
def ops_ping():
    return jsonify({"ok": True, "node_id": _node_id(), "ts": int(time.time())})

@bp_ops_ping.post("/ops/echo")
def ops_echo():
    data = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "received": data, "ts": int(time.time())})
# c=a+b



def register(app):
    app.register_blueprint(bp_ops_ping)
    return app
