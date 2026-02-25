# -*- coding: utf-8 -*-
"""routes/admin_usb_runner.py - UI/API dlya Local-only Job Runner + Shablony/Master/Validatsiya.

Marshruty (added):
  • GET /admin/usb_runner/templates - spisok shablonov
  • POST /admin/usb_runner/preview - prevyu/validatsiya (iz shablona or iz job)
  • POST /admin/usb_runner/create - zapis job na USB (AB=A → dry)
  • POST /admin/usb_runner/validate - validatsiya syrogo JSON-teksta (textarea)

# c=a+b"""
from __future__ import annotations
import json, os, secrets, time
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

from modules.usb_runner.jobs import detect_usb_root, list_jobs, load_job, finalize_job, write_local_log  # type: ignore
from modules.usb_runner.executor import execute  # type: ignore
from modules.usb_runner.templates import list_templates as tmpl_list, render_template as tmpl_render, preview_job  # type: ignore
from modules.usb_runner.validator import validate_text  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_usb = Blueprint("admin_usb_runner", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _ester_jobs_dir(usb: Path) -> Path:
    return (usb / "ESTER" / "jobs")

def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

@bp_usb.get("/admin/usb_runner")
def page():
    return render_template("admin_usb_runner.html", ab=AB)

@bp_usb.get("/admin/usb_runner/status")
def status():
    usb = detect_usb_root()
    if not usb:
        return jsonify({"ok": False, "error": "usb-not-found"}), 404
    lim = int(os.getenv("USB_RUNNER_MAX_JOBS","50"))
    return jsonify(list_jobs(usb, lim))

@bp_usb.post("/admin/usb_runner/execute")
def run():
    body = request.get_json(silent=True) or {}
    usb = Path(body.get("mount")) if body.get("mount") else (detect_usb_root() or None)
    if not usb:
        return jsonify({"ok": False, "error": "usb-not-found"}), 404
    limit = int(body.get("limit", int(os.getenv("USB_RUNNER_MAX_JOBS","50"))))
    filter_types = [str(t).lower().strip() for t in (body.get("types") or []) if str(t).strip()]
    q = list_jobs(usb, limit)
    items = q.get("items") or []
    results = []
    for j in items[:limit]:
        if filter_types and (str(j.get("type") or "").lower() not in filter_types):
            continue
        res = execute(j, usb, {})
        results.append({"uid": j.get("uid"), "type": j.get("type"), "result": res})
        try:
            write_local_log("usb_runner", {"job": j, "result": res})
            finalize_job(usb, j, res)
        except Exception:
            pass
    return jsonify({"ok": True, "processed": len(results), "items": results})

# --- Templates/Wizard ---
@bp_usb.get("/admin/usb_runner/templates")
def api_templates():
    if os.getenv("USB_RUNNER_TEMPLATES_ENABLE","1") != "1":
        return jsonify({"ok": False, "error": "disabled"}), 403
    return jsonify(tmpl_list())

@bp_usb.post("/admin/usb_runner/preview")
def api_preview():
    if os.getenv("USB_RUNNER_TEMPLATES_ENABLE","1") != "1":
        return jsonify({"ok": False, "error": "disabled"}), 403
    usb = detect_usb_root()
    if not usb:
        return jsonify({"ok": False, "error": "usb-not-found"}), 404
    body = request.get_json(silent=True) or {}
    if "template" in body:
        try:
            job = tmpl_render(str(body.get("template")), body.get("params") or {})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400
    else:
        job = body.get("job") or {}
    prev = preview_job(job, usb)
    return jsonify({"ok": True, "job": job, "preview": prev})

@bp_usb.post("/admin/usb_runner/create")
def api_create():
    if os.getenv("USB_RUNNER_TEMPLATES_ENABLE","1") != "1":
        return jsonify({"ok": False, "error": "disabled"}), 403
    usb = detect_usb_root()
    if not usb:
        return jsonify({"ok": False, "error": "usb-not-found"}), 404
    body = request.get_json(silent=True) or {}
    if "template" in body:
        job = tmpl_render(str(body.get("template")), body.get("params") or {})
    else:
        job = body.get("job") or {}
    prev = preview_job(job, usb)
    if not prev.get("ok"):
        return jsonify({"ok": False, "error": "preview-failed", "preview": prev}), 400
    ts = int(time.time())
    jtype = (job.get("type") or "job").lower()
    name = f"{ts}-{jtype}-{secrets.token_hex(2)}.json"
    path = _ester_jobs_dir(usb) / name
    if AB == "B":
        _write_json(path, job)
        return jsonify({"ok": True, "written": str(path), "name": name, "job": job})
    else:
        return jsonify({"ok": True, "dry": True, "would_write": str(path), "name": name, "job": job})

@bp_usb.post("/admin/usb_runner/validate")
def api_validate():
    usb = detect_usb_root()
    if not usb:
        return jsonify({"ok": False, "error": "usb-not-found"}), 404
    body = request.get_json(silent=True) or {}
    text = str(body.get("text") or "")
    res = validate_text(text, usb)
    return jsonify(res)

def register_admin_usb_runner(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_usb)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_usb_runner_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb_runner")
        def _p(): return page()
        @pref.get("/admin/usb_runner/status")
        def _s(): return status()
        @pref.post("/admin/usb_runner/execute")
        def _e(): return run()
        @pref.get("/admin/usb_runner/templates")
        def _t(): return api_templates()
        @pref.post("/admin/usb_runner/preview")
        def _pr(): return api_preview()
        @pref.post("/admin/usb_runner/create")
        def _cr(): return api_create()
        @pref.post("/admin/usb_runner/validate")
        def _va(): return api_validate()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_usb)
    return app