# -*- coding: utf-8 -*-
"""
routes/metrics_mind_routes.py — metriki myshleniya (Prometheus exposition).
  • /metrics/mind

Eksportiruem:
  - mind_run_ok_total
  - mind_run_err_total
  - mind_action_total{kind="..."}
  - mind_blocked_total{kind="..."}
  - mind_last_timestamp_seconds

Mosty:
- Yavnyy: (Nablyudaemost v†" Myshlenie) vidimost prinyatykh/zablokirovannykh resheniy.
- Skrytyy #1: (Kibernetika v†" R egulyatsiya) po metrikam mozhno nastraivat kvoty/prioritety.
- Skrytyy #2: (Inzheneriya v†" Ekspluatatsiya) drop-in, otdelnyy endpoint.

Zemnoy abzats:
Eto schetchik u pulta: skolko resheniy proshlo, gde probki, kogda posledniy raz dumali.

# c=a+b
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Blueprint, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_metrics_mind = Blueprint("metrics_mind", __name__)

_STATE = Path(os.getcwd()) / "data" / "rulehub" / "state.json"

def register(app):
    app.register_blueprint(bp_metrics_mind)

@bp_metrics_mind.route("/metrics/mind", methods=["GET"])
def metrics_mind():
    st = {"counters": {}, "last_ts": 0}
    if _STATE.exists():
        try:
            st = json.loads(_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    lines = []
    c = st.get("counters", {})
    lines.append(f'mind_run_ok_total {int(c.get("run.ok", 0))}')
    lines.append(f'mind_run_err_total {int(c.get("run.err", 0))}')
    # action.* i blocked.*
    for k, v in c.items():
        if k.startswith("action."):
            kind = k.split(".", 1)[1].replace('"', '\\"')
            lines.append(f'mind_action_total{{kind="{kind}"}} {int(v)}')
        if k.startswith("blocked."):
            kind = k.split(".", 1)[1].replace('"', '\\"')
            lines.append(f'mind_blocked_total{{kind="{kind}"}} {int(v)}')
    lines.append(f'mind_last_timestamp_seconds {int(st.get("last_ts", 0))}')
    body = "\n".join(lines) + "\n"
    return Response(body, mimetype="text/plain; version=0.0.4; charset=utf-8")
