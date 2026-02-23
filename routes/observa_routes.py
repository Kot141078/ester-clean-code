# -*- coding: utf-8 -*-
"""
routes/observa_routes.py - /healthz, /metrics i prostaya panel nablyudaemosti.

Mosty:
- Yavnyy: (Operatsii ↔ Nablyudaemost) bystryy srez sostoyaniya bez vneshnikh sistem.
- Skrytyy #1: (Kibernetika ↔ Kontrol) eksponiruem klyuchevye tsifry (disk/pamyat/ostorozhnost).
- Skrytyy #2: (Vyzhivanie ↔ Signaly) v buduschem syuda udobno prikrutit alerty.

Zemnoy abzats:
Eto «termometr i puls»: esli temperatura vyshla za ramki - lechim, poka ne pozdno.

# c=a+b
"""
from __future__ import annotations
import os, shutil, json
from flask import Blueprint, jsonify, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_obs = Blueprint("observa", __name__, template_folder="../templates", static_folder="../static")
OBS_AB = (os.getenv("OBS_AB","A") or "A").upper()
NS = os.getenv("METRICS_NS","ester")

def register(app):
    app.register_blueprint(bp_obs)

def _caution_status():
    try:
        from modules.policy.cautious_freedom import status as _st  # type: ignore
        return _st()
    except Exception:
        return {"ok": False}

@bp_obs.route("/healthz", methods=["GET"])
def healthz():
    total, used, free = shutil.disk_usage(".")
    mem = None
    try:
        import resource
        mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        mem = -1
    caut = _caution_status()
    ok = free > 200*1024*1024  # >200MB
    return jsonify({"ok": ok, "disk_free": free, "disk_total": total, "rss_kb": mem, "caution_ok": bool(caut.get("ok",True))})

@bp_obs.route("/metrics", methods=["GET"])
def metrics():
    if OBS_AB == "B":
        return ("# metrics disabled by OBS_AB=B\n", 200, {"Content-Type":"text/plain; charset=utf-8"})
    total, used, free = shutil.disk_usage(".")
    lines = []
    lines.append(f'{NS}_disk_free_bytes {free}')
    lines.append(f'{NS}_disk_total_bytes {total}')
    try:
        import resource
        lines.append(f'{NS}_process_rss_kb {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}')
    except Exception:
        lines.append(f'{NS}_process_rss_kb -1')
    try:
        from modules.policy.cautious_freedom import status as _st  # type: ignore
        st = _st()
        lines.append(f'{NS}_caution_rules_count {int(st.get("rules_count",0))}')
        lines.append(f'{NS}_caution_enabled {1 if st.get("enabled",True) else 0}')
    except Exception:
        lines.append(f'{NS}_caution_enabled 0')
    body = "\n".join(lines) + "\n"
    return (body, 200, {"Content-Type":"text/plain; charset=utf-8"})

@bp_obs.route("/admin/observa", methods=["GET"])
def admin_observa():
    return render_template("observa_console.html")
# c=a+b