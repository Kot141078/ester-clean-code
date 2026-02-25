# -*- coding: utf-8 -*-
"""routes/selfcheck.py - UI/REST panel “Self-Check”.

Route:
  • GET /admin/selfcheck - HTML
  • GET /admin/selfcheck/status - run_checks()
  • POST /admin/selfcheck/recheck - to zhe, what status (dlya udobstva knopki)
  • POST /admin/selfcheck/fix - primenit bezopasnye fiksy (AB-aware)

Mosty:
- Yavnyy (UX ↔ Kibernetika): v odnom meste proverka i “pochinka po mestu”.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): dry-run v AB=A, yavnye otchety o kazhdoy operatsii.
- Skrytyy 2 (Praktika ↔ Sovmestimost): ne menyaet kontrakty i sloty, tolko ekspluatatsionnye veschi.

Zemnoy abzats:
This is “panel tekhosmotra”: proverili - uvideli krasnye zony - po knopke lokalno popravili.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.selfcheck.selfcheck import run_checks, apply_fixes  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_sc = Blueprint("selfcheck", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_sc.get("/admin/selfcheck")
def page():
    return render_template("selfcheck.html", ab=AB)

@bp_sc.get("/admin/selfcheck/status")
def status():
    return jsonify({"ok": True, "ab": AB, "checks": run_checks()})

@bp_sc.post("/admin/selfcheck/recheck")
def recheck():
    return jsonify({"ok": True, "ab": AB, "checks": run_checks()})

@bp_sc.post("/admin/selfcheck/fix")
def fix():
    body = request.get_json(silent=True) or {}
    rep = apply_fixes(body)
    return jsonify({"ok": bool(rep.get("ok")), "ab": AB, "result": rep})

def register_selfcheck(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_sc)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("selfcheck_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/selfcheck")
        def _p(): return page()

        @pref.get("/admin/selfcheck/status")
        def _s(): return status()

        @pref.post("/admin/selfcheck/recheck")
        def _r(): return recheck()

        @pref.post("/admin/selfcheck/fix")
        def _f(): return fix()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_sc)
    return app