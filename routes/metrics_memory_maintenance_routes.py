# -*- coding: utf-8 -*-
"""routes/metrics_memory_maintenance_routes.py - Prometheus metrics obsluzhivaniya pamyati.

Endpoint:
  • GET /metrics/memory_maintenance

Mosty:
- Yavnyy: (Nablyudaemost v†" Memory) vidim posledniy zapusk Re statusy shagov.
- Skrytyy #1: (Kibernetika v†" Planirovanie) mozhno alertit na "davno ne bylo snapshota".
- Skrytyy #2: (Inzheneriya v†" Nadezhnost) otdelnyy put ne konfliktuet s drugimi metrikami.

Zemnoy abzats:
Nebolshoy tablo: kogda v posledniy raz ubrali i chto poluchilos.

# c=a+b"""
from __future__ import annotations

import json
import os
from flask import Blueprint, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_metrics_mem_maint = Blueprint("metrics_mem_maint", __name__)

_STATE = os.path.join("data", "mem_maint", "state.json")

def register(app):
    app.register_blueprint(bp_metrics_mem_maint)

@bp_metrics_mem_maint.route("/metrics/memory_maintenance", methods=["GET"])
def metrics():
    if not os.path.isfile(_STATE):
        return Response("mem_maint_last_ts 0\nmem_maint_last_ok 0\n", mimetype="text/plain; version=0.0.4; charset=utf-8")
    try:
        st = json.load(open(_STATE, "r", encoding="utf-8"))
    except Exception:
        return Response("mem_maint_last_ts 0\nmem_maint_last_ok 0\n", mimetype="text/plain; version=0.0.4; charset=utf-8")
    ts = int(st.get("ts", 0) or 0)
    ok = 1 if all(s.get("ok") for s in (st.get("steps") or [])) else 0
    lines = [f"mem_maint_last_ts {ts}", f"mem_maint_last_ok {ok}"]
# return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4; charset=utf-8")