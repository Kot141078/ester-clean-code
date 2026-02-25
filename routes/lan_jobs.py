# -*- coding: utf-8 -*-
"""routes/lan_jobs.py - UI/REST: ochered zadach LAN.

Route:
  • GET /admin/lan/jobs - HTML
  • GET /admin/lan/jobs/status - ochered + metrics
  • POST /admin/lan/jobs/enqueue_pull - {peer, pri?}
  • POST /admin/lan/jobs/enqueue_offer
  • POST /admin/lan/jobs/clear

Mosty:
- Yavnyy (UX ↔ Orkestratsiya): edinaya panel zadach seti.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): vidny popytki/statusy/kvoty.
- Skrytyy 2 (Praktika ↔ Sovmestimost): interfeysy prostye JSON - legko dergat iz skriptov.

Zemnoy abzats:
Zdes stavim zadaniya “zabrat/otdat” i sledim, chtoby vse shlo po normam i bez shtorma.

# c=a+b"""
from __future__ import annotations
import json, os
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

from modules.lan.job_queue import enqueue, clear_finished  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
JQ = STATE_DIR / "lan_jobs.json"

bp_lanj = Blueprint("lan_jobs", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _load_json(p: Path):
    try:
        if p.exists(): return json.loads(p.read_text(encoding="utf-8"))
    except Exception: pass
    return {}

@bp_lanj.get("/admin/lan/jobs")
def page():
    return render_template("lan_jobs.html", ab=AB)

@bp_lanj.get("/admin/lan/jobs/status")
def status():
    q = _load_json(JQ)
    return jsonify({"ok": True, "ab": AB, "queue": q})

@bp_lanj.post("/admin/lan/jobs/enqueue_pull")
def enq_pull():
    body = request.get_json(silent=True) or {}
    peer = (body.get("peer") or "").strip()
    if not peer: return jsonify({"ok": False, "error": "no-peer"}), 400
    pri = int(body.get("pri", 100))
    jid = enqueue({"type":"pull","args":{"peer": peer},"pri": pri})
    return jsonify({"ok": True, "id": jid})

@bp_lanj.post("/admin/lan/jobs/enqueue_offer")
def enq_offer():
    pri = int((request.get_json(silent=True) or {}).get("pri", 100))
    jid = enqueue({"type":"offer","args":{},"pri": pri})
    return jsonify({"ok": True, "id": jid})

@bp_lanj.post("/admin/lan/jobs/clear")
def clear():
    clear_finished()
    return jsonify({"ok": True})

def register_lan_jobs(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_lanj)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("lan_jobs_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/lan/jobs")
        def _p(): return page()

        @pref.get("/admin/lan/jobs/status")
        def _s(): return status()

        @pref.post("/admin/lan/jobs/enqueue_pull")
        def _ep(): return enq_pull()

        @pref.post("/admin/lan/jobs/enqueue_offer")
        def _eo(): return enq_offer()

        @pref.post("/admin/lan/jobs/clear")
        def _c(): return clear()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_lanj)
    return app