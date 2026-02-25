# -*- coding: utf-8 -*-
"""routes/resource_scheduler.py - UI/REST “Resursnyy planirovschik LLM”.

Route:
  • GET /admin/resources/scheduler - HTML
  • GET /admin/resources/scheduler/status - status()
  • POST /admin/resources/scheduler/choose - vybrat resources pod req
  • POST /admin/resources/scheduler/run - prognat prompt cherez alias (AB-aware)

Mosty:
- Yavnyy (UX ↔ Orkestratsiya): v odnom meste - vybor i zapusk.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): kvoty/meter i treys-log prozrachno vidny.
- Skrytyy 2 (Praktika ↔ Sovmestimost): OpenAI-sovmestimyy vyzov lokalnykh resursov; yadro ne trogaem.

Zemnoy abzats:
Eto “panel dispetchera”: podbiraem luchshuyu lokalnuyu model po trebovaniyam i zapuskaem ee v odin klik, ne narushaya limitov.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.resources.scheduler_settings import load_rs_settings, save_rs_settings, load_meter  # type: ignore
from modules.resources.scheduler import status as sched_status, choose_resource, run_via_resource  # type: ignore
from modules.resources.trace_log import list_traces  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_rsch = Blueprint("resource_scheduler", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_rsch.get("/admin/resources/scheduler")
def page():
    return render_template("resource_scheduler.html", ab=AB)

@bp_rsch.get("/admin/resources/scheduler/status")
def api_status():
    st = sched_status(); m = load_meter()
    return jsonify({"ok": True, "ab": AB, "status": st, "meter": m, "traces": list_traces(50)})

@bp_rsch.post("/admin/resources/scheduler/choose")
def api_choose():
    body = request.get_json(silent=True) or {}
    rep = choose_resource(body)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

@bp_rsch.post("/admin/resources/scheduler/run")
def api_run():
    body = request.get_json(silent=True) or {}
    alias = (body.get("alias") or "").strip()
    prompt = (body.get("prompt") or "").strip()
    max_tokens = int(body.get("max_tokens", 64))
    temperature = float(body.get("temperature", 0.0))
    if not alias or not prompt:
        return jsonify({"ok": False, "error": "alias/prompt required"}), 400
    rep = run_via_resource(alias, prompt, max_tokens=max_tokens, temperature=temperature)
    return jsonify({"ok": bool(rep.get("ok")), "ab": AB, "result": rep})

def register_resource_scheduler(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_rsch)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("resource_scheduler_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/resources/scheduler")
        def _p(): return page()

        @pref.get("/admin/resources/scheduler/status")
        def _s(): return api_status()

        @pref.post("/admin/resources/scheduler/choose")
        def _c(): return api_choose()

        @pref.post("/admin/resources/scheduler/run")
        def _r(): return api_run()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_rsch)
    return app