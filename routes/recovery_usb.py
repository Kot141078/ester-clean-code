# -*- coding: utf-8 -*-
"""routes/recovery_usb.py - UI/REST “Recovery USB” (plan i sborka oflayn-fleshki).

Route:
  • GET /admin/recovery - HTML
  • GET /admin/recovery/status - USB toma + lokalnye pakety/installyatory
  • POST /admin/recovery/plan - {mount, options?} → plan_recovery_usb
  • POST /admin/recovery/build - {mount, options?} → build_recovery_usb (AB-aware)

Mosty:
- Yavnyy (UX ↔ Ekspluatatsiya): knopka “Sobrat Recovery USB” dlya bystroy oflayn-razdachi Ester.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): dry-plan v A - bez zapisi; predskazuemyy spisok artefaktov.
- Skrytyy 2 (Praktika ↔ Sovmestimost): skripty pod Win/macOS/Linux; yadro Ester ne trogaem.

Zemnoy abzats:
This is “master fleshki”: sobiraet na USB vse nuzhnoe - instruktsii, skripty, pakety, (opts.) installyator LM Studio.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.usb.recovery import list_usb_targets  # type: ignore
from modules.recovery.builder import status as rec_status, plan_recovery_usb, build_recovery_usb  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_rec = Blueprint("recovery_usb", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_rec.get("/admin/recovery")
def page():
    return render_template("recovery_usb.html", ab=AB)

@bp_rec.get("/admin/recovery/status")
def status():
    return jsonify({
        "ok": True, "ab": AB,
        "usb": list_usb_targets(),
        "local": rec_status()
    })

@bp_rec.post("/admin/recovery/plan")
def plan():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    options = body.get("options") or {}
    if not mount: return jsonify({"ok": False, "error": "mount required"}), 400
    return jsonify(plan_recovery_usb(mount, options))

@bp_rec.post("/admin/recovery/build")
def build():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    options = body.get("options") or {}
    if not mount: return jsonify({"ok": False, "error": "mount required"}), 400
    return jsonify(build_recovery_usb(mount, options))

def register_recovery_usb(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_rec)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("recovery_usb_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/recovery")
        def _p(): return page()

        @pref.get("/admin/recovery/status")
        def _s(): return status()

        @pref.post("/admin/recovery/plan")
        def _pl(): return plan()

        @pref.post("/admin/recovery/build")
        def _b(): return build()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_rec)
    return app