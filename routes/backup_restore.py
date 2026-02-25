# -*- coding: utf-8 -*-
"""routes/backup_restore.py - UI/REST: eksport/import nastroek Re "Sozdat fleshku-repliku".

Route:
  • GET /admin/backup - HTML.
  • GET /admin/backup/export - JSON-backup.
  • POST /admin/backup/import - body {json_text, mode:'merge'|'replace'} v†' primenit.
  • POST /admin/backup/usb/replica - body {mount} v†' sozdat strukturu ESTER/ (AB=A v†' dry).

Mosty:
- Yavnyy (Arkhitektura v†" UX): odin ekran - sdelat bekap, vosstanovit, zapisat fleshku.
- Skrytyy 1 (Infoteoriya v†" Prozrachnost): rezhim AB MODE otrazhen v otvetakh; plany pered zapisyu.
- Skrytyy 2 (Praktika v†" Sovmestimost): replika sovmestima s nashim USB portable-deploem (kind="dump").

Zemnoy abzats:
This is “stranitsa tekhobsluzhivaniya”: sdelal snimok, perenes na fleshku, vosstanovil na drugom uzle bez seti.

# c=a+b"""
from __future__ import annotations

import json
import os
from flask import Blueprint, jsonify, render_template, request

from modules.backup.backup_logic import export_state, import_state  # type: ignore
from modules.usb.usb_replica import make_replica  # type: ignore
from modules.usb.usb_probe import list_targets  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_backup = Blueprint("backup_restore", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_backup.get("/admin/backup")
def page():
    return render_template("backup_restore.html", ab=AB)

@bp_backup.get("/admin/backup/export")
def api_export():
    return jsonify({"ok": True, "ab": AB, "backup": export_state()})

@bp_backup.post("/admin/backup/import")
def api_import():
    data = request.get_json(silent=True) or {}
    text = data.get("json_text") or ""
    mode = (data.get("mode") or "merge").lower()
    if AB != "B":
        # just a plan - let's try to parse Re and return what *would* be used
        try:
            b = json.loads(text)
        except Exception:
            return jsonify({"ok": False, "error": "bad-json"}), 400
        files = (b.get("files") or {})
        plan = {"mode": mode, "would_apply": list(files.keys())}
        return jsonify({"ok": True, "ab": AB, "plan": plan})
    # mode B - real recording
    try:
        b = json.loads(text)
    except Exception:
        return jsonify({"ok": False, "error": "bad-json"}), 400
    rep = import_state(b, mode=mode)
    return jsonify({"ok": bool(rep.get("ok")), "ab": AB, "result": rep})

@bp_backup.post("/admin/backup/usb/replica")
def api_usb_replica():
    data = request.get_json(silent=True) or {}
    mount = data.get("mount") or ""
    dry = (AB != "B")
    rep = make_replica(mount, dry=dry)
    return jsonify({"ok": bool(rep.get("ok")), "ab": AB, "result": rep})

@bp_backup.get("/admin/backup/targets")
def api_targets():
    return jsonify({"ok": True, "targets": list_targets()})

def register_backup_restore(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_backup)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("backup_restore_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/backup")
        def _p(): return page()

        @pref.get("/admin/backup/export")
        def _e(): return api_export()

        @pref.post("/admin/backup/import")
        def _i(): return api_import()

        @pref.post("/admin/backup/usb/replica")
        def _u(): return api_usb_replica()

        @pref.get("/admin/backup/targets")
        def _t(): return api_targets()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_backup)
    return app