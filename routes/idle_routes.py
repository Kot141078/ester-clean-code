# -*- coding: utf-8 -*-
"""
REST-upravlenie kholostym myslitelnym tsiklom.

Puti:
  POST /idle/start            - zapustit potok
  POST /idle/stop             - ostanovit potok
  GET  /idle/status           - status
  POST /idle/config           - {mode, gpu_mode} -> primenit

MOSTY:
- Yavnyy: Volya Ester ↔ Protsessy - «rezhisser» upravlyaet potokom mysley.
- Skrytyy 1: Operatsii ↔ Diagnostika - status/logi dostupny prostym JSON.
- Skrytyy 2: UI/Health ↔ Nadezhnost - otdelnyy blyuprint, bez konfliktov imen.

ZEMNOY ABZATs:
Eto kak pult u elektrostantsii: knopki «start/stop», regulyatory «tikho/v pol».
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.thinking.idle_engine import (
        idle_start, idle_stop, idle_status, idle_configure
    )
except Exception:
    # esli modul esche ne sobralsya - bezopasnaya zaglushka
    def _na(*args, **kwargs):
        return {"running": False, "error": "idle_engine not available"}
    idle_start = idle_stop = idle_status = _na  # type: ignore
    def idle_configure(cfg):  # type: ignore
        return {"ok": False, "error": "idle_engine not available", "cfg": cfg}

bp = Blueprint("idle_routes", __name__, url_prefix="/idle")

@bp.post("/start")
def _start():
    return jsonify({"ok": True, **idle_start()})

@bp.post("/stop")
def _stop():
    return jsonify({"ok": True, **idle_stop()})

@bp.get("/status")
def _status():
    return jsonify({"ok": True, **idle_status()})

@bp.post("/config")
def _config():
    data = request.get_json(silent=True) or {}
    res = idle_configure({
        "mode": data.get("mode", None),
        "gpu_mode": data.get("gpu_mode", None),
    })
    return jsonify({"ok": True, "config": res})

def register(app):
    app.register_blueprint(bp)
    return "idle_routes"

# c=a+b