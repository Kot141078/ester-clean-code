# -*- coding: utf-8 -*-
"""
routes/usb_autostart.py — UI/REST dlya upravleniya avtozapuskom USB-agenta.

Marshruty:
  • GET  /admin/usb/autostart             — HTML
  • GET  /admin/usb/autostart/status      — JSON: status, tekuschiy plan
  • POST /admin/usb/autostart/install     — ustanovit (AB=A v†' dry)
  • POST /admin/usb/autostart/uninstall   — udalit (AB=A v†' dry)

Mosty:
- Yavnyy (Kibernetika v†" UX): odna panel «vkl/vykl» avtozapuska.
- Skrytyy 1 (Infoteoriya v†" Nadezhnost): vyvodim plan Re artefakty, chtoby vse prozrachno.
- Skrytyy 2 (Praktika v†" Vezopasnost): A-rezhim ne pishet v sistemu.

Zemnoy abzats:
Knopka «Postavit dezhurnuyu sestru na post»: vklyuchil — ona sama nachnet obkhody pri vkhode v sistemu.

# c=a+b
"""
from __future__ import annotations

import os
from flask import Blueprint, jsonify, render_template, request

from modules.selfmanage.autostart_manager import plan_install, apply_install, plan_uninstall, apply_uninstall, status as st  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_usb_autostart = Blueprint("usb_autostart", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_usb_autostart.get("/admin/usb/autostart")
def page():
    return render_template("usb_autostart.html", ab=AB)

@bp_usb_autostart.get("/admin/usb/autostart/status")
def api_status():
    return jsonify({"ok": True, "ab": AB, "status": st()})

@bp_usb_autostart.post("/admin/usb/autostart/install")
def api_install():
    dry = (AB != "B")
    plan = plan_install()
    rep = apply_install(plan, dry=dry)
    return jsonify({"ok": bool(rep.get("ok")), "ab": AB, "plan": _simplify(plan), "result": rep})

@bp_usb_autostart.post("/admin/usb/autostart/uninstall")
def api_uninstall():
    dry = (AB != "B")
    plan = plan_uninstall()
    rep = apply_uninstall(plan, dry=dry)
    return jsonify({"ok": bool(rep.get("ok")), "ab": AB, "plan": _simplify(plan), "result": rep})

def _simplify(plan):
    # udobnyy vid dlya UI
    arts = [{"path": str(a.path), "kind": a.kind} for a in plan.get("artifacts", [])]
    return {"os": plan.get("os"), "artifacts": arts, "commands": plan.get("commands")}
    

def register_usb_autostart(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_usb_autostart)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("usb_autostart_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb/autostart")
        def _p():
            return page()

        @pref.get("/admin/usb/autostart/status")
        def _ps():
            return api_status()

        @pref.post("/admin/usb/autostart/install")
        def _pi():
            return api_install()

        @pref.post("/admin/usb/autostart/uninstall")
        def _pu():
            return api_uninstall()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_usb_autostart)
    return app