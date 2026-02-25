# -*- coding: utf-8 -*-
"""routes/admin_portable_oneclick.py - One-Click USB: predprosmotr i zapis perenosimoy struktury na fleshku.

Route:
  • GET /admin/portable/oneclick - stranitsa
  • GET /admin/portable/oneclick/status - sys_detect + nalichie USB
  • POST /admin/portable/oneclick/preview - poluchit plan faylov
  • POST /admin/portable/oneclick/apply - primenit plan (AB=A → dry)

Mosty:
- Yavnyy (UX → Fayly): odnoy knopkoy zapolnyaem ESTER/ neobkhodimymi artefaktami.
- Skrytyy 1 (Infoteoriya): baseline vstraivaetsya srazu, snizhaya entropiyu perenosov.
- Skrytyy 2 (Praktika): zapis tolko pod AB=B; without formatirovaniya/MBR.

Zemnoy abzats:
This is “sborochnyy press”: gotovit chemodan na fleshke tak, chtoby na drugoy machine byl tikhiy start.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template

from modules.portable.oneclick import sys_detect, preview, apply_plan, build_plan  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_portable_oneclick", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _usb_present() -> bool:
    try:
        from modules.portable.oneclick import _detect_usb_root  # type: ignore
        return bool(_detect_usb_root())
    except Exception:
        return False

@bp.get("/admin/portable/oneclick")
def page():
    return render_template("admin_portable_oneclick.html", ab=AB)

@bp.get("/admin/portable/oneclick/status")
def status():
    return jsonify({"ok": True, "ab": AB, "sys": sys_detect(), "usb": _usb_present()})

@bp.post("/admin/portable/oneclick/preview")
def preview_plan():
    return jsonify(preview())

@bp.post("/admin/portable/oneclick/apply")
def apply():
    plan = build_plan()
    res = apply_plan(plan)
    code = 200 if res.get("ok") else 400
    return jsonify({"ok": bool(res.get("ok")), "ab": AB, "result": res, "plan_len": len(plan.get("files", []))}), code

def register_admin_portable_oneclick(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_portable_oneclick_pref", __name__, url_prefix=url_prefix)
        @pref.get("/admin/portable/oneclick")
        def _p(): return page()
        @pref.get("/admin/portable/oneclick/status")
        def _s(): return status()
        @pref.post("/admin/portable/oneclick/preview")
        def _pr(): return preview_plan()
        @pref.post("/admin/portable/oneclick/apply")
        def _ap(): return apply()
        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app