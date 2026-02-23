# -*- coding: utf-8 -*-
"""
routes/admin_reports.py - panel otchetov.

Marshruty:
  • GET  /admin/reports                   - HTML
  • GET  /admin/reports/status            - spisok lokalnykh otchetov + podskazka po USB
  • POST /admin/reports/build             - {include_raw?, limit?, export_usb?, usb_mount?} → build_report()
  • GET  /admin/reports/download          - ?name=<file> → otdat lokalnyy otchet iz ~/.ester/reports/

Mosty:
- Yavnyy (UX ↔ Report Builder): odna knopka sobiraet otchet i, pri neobkhodimosti, kladet kopiyu na fleshku.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): status pokazyvaet, kuda sokhranili i chto voshlo.
- Skrytyy 2 (Praktika ↔ Sovmestimost): nikakoy lomki kontraktov, prostye JSON-fayly.

Zemnoy abzats:
Eto kak «knopka snyat pokazaniya priborov»: odnim nazhatiem fiksiruem sostoyanie tsekha i kladem v papku.

# c=a+b
"""
from __future__ import annotations
import os
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request, send_file, abort
from modules.reports.builder import build_report, list_reports  # type: ignore
from modules.reports.sources import find_usb_reports_root  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_reports = Blueprint("admin_reports", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_reports.get("/admin/reports")
def page():
    return render_template("admin_reports.html", ab=AB)

@bp_reports.get("/admin/reports/status")
def status():
    xs = list_reports(limit=100)
    usb = find_usb_reports_root("ESTER")
    return jsonify({"ok": True, "ab": AB, "local": xs, "usb_dir": (str(usb) if usb else None)})

@bp_reports.post("/admin/reports/build")
def api_build():
    body = request.get_json(silent=True) or {}
    include_raw = bool(body.get("include_raw", int(os.getenv("REPORTS_INCLUDE_RAW","0"))==1))
    limit = int(body.get("limit", int(os.getenv("REPORTS_MAX_ITEMS","200"))))
    export_usb = body.get("export_usb")
    usb_mount = (body.get("usb_mount") or "").strip() or None
    # Primechanie: usb_mount seychas ispolzuetsya v sources.find_usb_reports_root() cherez ENV-put (minimum svyaznosti)
    if usb_mount:
        os.environ["PORTABLE_DEST_LABEL"] = Path(usb_mount).name  # myagkaya podskazka
    res = build_report({"include_raw": include_raw, "limit": limit, "export_usb": export_usb})
    return jsonify(res)

@bp_reports.get("/admin/reports/download")
def download():
    name = (request.args.get("name") or "").strip()
    if not name or not name.endswith("-report.json"):
        return abort(400)
    try:
        state_dir = Path(os.path.expanduser(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))))
        local_dir = state_dir / "reports"
        path = (local_dir / name).resolve()
        if not str(path).startswith(str(local_dir.resolve())):
            return abort(403)
        if not path.exists():
            return abort(404)
        return send_file(str(path), mimetype="application/json", as_attachment=True, download_name=name)
    except Exception:
        return abort(500)

def register_admin_reports(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_reports)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_reports_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/reports")
        def _p(): return page()

        @pref.get("/admin/reports/status")
        def _s(): return status()

        @pref.post("/admin/reports/build")
        def _b(): return api_build()

        @pref.get("/admin/reports/download")
        def _d(): return download()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_reports)
    return app