# -*- coding: utf-8 -*-
"""routes/projects.py - panel project: sozdanie, addavlenie zadach, batch-progon, eksport na fleshku.

Route:
  • GET /admin/projects - HTML
  • GET /admin/projects/status - spisok proektov + put inboksa
  • GET /admin/projects/detail - details project ?id=
  • POST /admin/projects/create - {name, defaults?}
  • POST /admin/projects/add_jobs - {id, items:[{prompt, alias?, req?, max_tokens?, temperature?}]}
  • POST /admin/projects/run - {id, mode: pending|all, stop_on_error?}
  • POST /admin/projects/export - {id, mount}

Mosty:
- Yavnyy (UX ↔ Orkestratsiya): edinyy ekran dlya postanovki zadach i zapuska batchey.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): AB-aware rezhimy (dry vs real), statusy i protocol rezultatov v JSON.
- Skrytyy 2 (Praktika ↔ Sovmestimost): eksport v offlayn-strukturu ESTER/exports na fleshke, yadro ne trogaem.

Zemnoy abzats:
This is “rabochiy stol”: sozday proekt, vstav prompty, zapusti - i zaberi rezultaty na fleshku bez golovnoy boli.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.projects.project_store import list_projects, get_project, create_project, add_jobs, export_project, ensure_inbox  # type: ignore
from modules.projects.batch_runner import run_batch  # type: ignore
from modules.usb.recovery import list_usb_targets  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_proj = Blueprint("projects", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_proj.get("/admin/projects")
def page():
    return render_template("projects.html", ab=AB)

@bp_proj.get("/admin/projects/status")
def status():
    inbox = ensure_inbox().get("path","")
    return jsonify({"ok": True, "ab": AB, "projects": list_projects(), "inbox_path": inbox, "usb": list_usb_targets()})

@bp_proj.get("/admin/projects/detail")
def detail():
    pid = (request.args.get("id") or "").strip()
    if not pid: return jsonify({"ok": False, "error":"no-id"}), 400
    return jsonify(get_project(pid))

@bp_proj.post("/admin/projects/create")
def create():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()
    defaults = body.get("defaults") or None
    return jsonify(create_project(name, defaults))

@bp_proj.post("/admin/projects/add_jobs")
def add():
    body = request.get_json(silent=True) or {}
    pid = (body.get("id") or "").strip()
    items = body.get("items") or []
    if not pid or not items: return jsonify({"ok": False, "error":"id/items required"}), 400
    return jsonify(add_jobs(pid, items))

@bp_proj.post("/admin/projects/run")
def run():
    body = request.get_json(silent=True) or {}
    pid = (body.get("id") or "").strip()
    mode = (body.get("mode") or "pending").strip()
    stop = bool(body.get("stop_on_error", False))
    if not pid: return jsonify({"ok": False, "error":"id required"}), 400
    return jsonify(run_batch(pid, mode=mode, stop_on_error=stop))

@bp_proj.post("/admin/projects/export")
def export():
    body = request.get_json(silent=True) or {}
    pid = (body.get("id") or "").strip()
    mount = (body.get("mount") or "").strip()
    if not pid or not mount: return jsonify({"ok": False, "error":"id/mount required"}), 400
    return jsonify(export_project(pid, mount))

def register_projects(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_proj)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("projects_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/projects")
        def _p(): return page()

        @pref.get("/admin/projects/status")
        def _s(): return status()

        @pref.get("/admin/projects/detail")
        def _d(): return detail()

        @pref.post("/admin/projects/create")
        def _c(): return create()

        @pref.post("/admin/projects/add_jobs")
        def _a(): return add()

        @pref.post("/admin/projects/run")
        def _r(): return run()

        @pref.post("/admin/projects/export")
        def _e(): return export()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_proj)
    return app