# -*- coding: utf-8 -*-
"""routes/admin_jobs.py - UI/REST “LAN-Jobs”: lokalnaya ochered, zapusk, push na pir, prosmotr remote index.

Route:
  • GET /admin/jobs
  • GET /admin/jobs/status
  • POST /admin/jobs/run_once
  • POST /admin/jobs/push_proxy {base_url, type, args?, public?}
  • GET /admin/jobs/remote_index_proxy?base=http://...

Mosty:
- Yavnyy (UX ↔ Operatsii): operator vidit ochered i mozhet otpravit zadanie sosedu.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): proksi snimaet CORS i logiruet otvety.
- Skrytyy 2 (Praktika ↔ Sovmestimost): stdlib urllib; dry(A)/real(B).

Zemnoy abzats:
This is “pult zadach”: paru klikov - i sosed soberet tiket, a my potom ego zaberem iz ego diagnostics.

# c=a+b"""
from __future__ import annotations
import json, os, urllib.request, urllib.error
from flask import Blueprint, jsonify, render_template, request

from modules.jobs.queue import list_jobs  # type: ignore
from modules.jobs.executor import run_job  # type: ignore
from modules.jobs.queue import next_queued, update  # type: ignore
from modules.diag.signature import get_signature  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_jobs = Blueprint("admin_jobs", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_jobs.get("/admin/jobs")
def page():
    return render_template("admin_jobs.html", ab=AB)

@bp_jobs.get("/admin/jobs/status")
def status():
    j = list_jobs(limit=200)
    return jsonify({"ok": True, "ab": AB, "signature": get_signature(), "queue": j})

@bp_jobs.post("/admin/jobs/run_once")
def run_once():
    job = next_queued()
    if not job:
        return jsonify({"ok": True, "note": "no-queued"})
    update(job["id"], status="running")
    try:
        res = run_job(job)
        if res.get("ok"):
            update(job["id"], status="done", result=res, error=None)
        else:
            update(job["id"], status="error", result=res, error=res.get("error","unknown"))
    except Exception as e:
        update(job["id"], status="error", error=str(e))
    return jsonify({"ok": True})

@bp_jobs.post("/admin/jobs/push_proxy")
def push_proxy():
    body = request.get_json(silent=True) or {}
    base = (body.get("base_url") or "").rstrip("/")
    if not base: return jsonify({"ok": False, "error": "base_url required"}), 400
    payload = {
        "type": (body.get("type") or "").strip(),
        "args": body.get("args") or {},
        "public": bool(body.get("public", True)),
        "origin": get_signature()
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{base}/lan/jobs/push", data=data, headers={"Content-Type":"application/json","User-Agent":"EsterJobs/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            rep = json.loads(r.read().decode("utf-8"))
            return jsonify({"ok": True, "remote": rep})
    except urllib.error.URLError as e:
        return jsonify({"ok": False, "error": str(e)}), 502

@bp_jobs.get("/admin/jobs/remote_index_proxy")
def remote_index_proxy():
    base = (request.args.get("base") or "").rstrip("/")
    if not base: return jsonify({"ok": False, "error": "base required"}), 400
    req = urllib.request.Request(f"{base}/lan/jobs/index", headers={"User-Agent":"EsterJobs/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            rep = json.loads(r.read().decode("utf-8"))
            return jsonify(rep)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

def register_admin_jobs(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_jobs)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_jobs_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/jobs")
        def _p(): return page()

        @pref.get("/admin/jobs/status")
        def _s(): return status()

        @pref.post("/admin/jobs/run_once")
        def _r(): return run_once()

        @pref.post("/admin/jobs/push_proxy")
        def _pp(): return push_proxy()

        @pref.get("/admin/jobs/remote_index_proxy")
        def _rip(): return remote_index_proxy()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_jobs)
    return app