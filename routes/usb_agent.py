# -*- coding: utf-8 -*-
"""
routes/usb_agent.py — UI/REST upravleniya Zero-Touch USB agentom.

Marshruty:
  • GET  /admin/usb/agent            — HTML-stranitsa
  • GET  /admin/usb/agent/status     — JSON-status
  • POST /admin/usb/agent/start      — zapustit (opts. interval)
  • POST /admin/usb/agent/stop       — ostanovit
  • GET  /admin/usb/agent/logs       — khvost JSONL-logov (?tail=200)

Mosty:
- Yavnyy (Kibernetika v†" UX): operator upravlyaet agentom odnoy knopkoy.
- Skrytyy 1 (Infoteoriya v†" Nablyudenie): status+logi dayut vidimost protsessa.
- Skrytyy 2 (Praktika v†" Vezopasnost): po umolchaniyu agent vyklyuchen; start — yavnym deystviem.

Zemnoy abzats:
Eto «pult dezhurnoy»: vklyuchil obkhod — smotrish telemetriyu. Vyklyuchil — tishina.

# c=a+b
"""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from modules.listeners.usb_agent_runner import start as run_start, stop as run_stop, status as run_status  # type: ignore
from modules.selfmanage.usb_log import tail_lines  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_usb_agent = Blueprint("usb_agent", __name__)

@bp_usb_agent.get("/admin/usb/agent")
def page_agent():
    return render_template("usb_agent.html")

@bp_usb_agent.get("/admin/usb/agent/status")
def api_status():
    return jsonify(run_status())

@bp_usb_agent.post("/admin/usb/agent/start")
def api_start():
    interval = int((request.form.get("interval") or request.json.get("interval") if request.is_json else 0) or 0) or 5
    target = (request.form.get("mount") if not request.is_json else request.json.get("mount", "")) or None
    rep = run_start(interval=interval, target=target)
    return jsonify(rep)

@bp_usb_agent.post("/admin/usb/agent/stop")
def api_stop():
    return jsonify(run_stop())

@bp_usb_agent.get("/admin/usb/agent/logs")
def api_logs():
    tail = int((request.args.get("tail") or "200").strip() or "200")
    return jsonify({"ok": True, "tail": tail, "text": tail_lines(tail)})

def register_usb_agent(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_usb_agent)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("usb_agent_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb/agent")
        def _p():
            return page_agent()

        @pref.get("/admin/usb/agent/status")
        def _ps():
            return api_status()

        @pref.post("/admin/usb/agent/start")
        def _pst():
            return api_start()

        @pref.post("/admin/usb/agent/stop")
        def _sp():
            return api_stop()

        @pref.get("/admin/usb/agent/logs")
        def _pl():
            return api_logs()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_usb_agent)
    return app