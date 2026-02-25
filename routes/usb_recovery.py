# -*- coding: utf-8 -*-
"""routes/usb_recovery.py - UI/REST “USB-Recovery”.

Route:
  • GET /admin/usb/recovery - HTML
  • GET /admin/usb/recovery/status - cfg + spisok tomov
  • POST /admin/usb/recovery/scan - {mount} → kandidaty
  • POST /admin/usb/recovery/plan - {mount} → plan
  • POST /admin/usb/recovery/apply - {mount, health_cmd?} → vosstanovlenie (AB uvazhaet)
  • POST /admin/usb/recovery/save - sokhranit nastroyki

Mosty:
- Yavnyy (UX ↔ Bezopasnost): odin ekran - skan, plan, vosstanovlenie.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): dry-run v AB=A, proverki checksum i health v AB=B.
- Skrytyy 2 (Praktika ↔ Sovmestimost): uvazhaem A/B-sloty i suschestvuyuschie portable-puti.

Zemnoy abzats:
Eto “master pervoy pomoschi”: ukazhi fleshku - on vse sdelaet sam, akkuratno i s otkatom.

# c=a+b"""
from __future__ import annotations

import os
from flask import Blueprint, jsonify, render_template, request

from modules.usb.recovery_settings import load_usb_recovery_settings, save_usb_recovery_settings  # type: ignore
from modules.usb.recovery import list_usb_targets, scan_usb, plan_recover, apply_recover  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ur = Blueprint("usb_recovery", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_ur.get("/admin/usb/recovery")
def page():
    return render_template("usb_recovery.html", ab=AB)

@bp_ur.get("/admin/usb/recovery/status")
def status():
    return jsonify({"ok": True, "ab": AB, "settings": load_usb_recovery_settings(), "targets": list_usb_targets()})

@bp_ur.post("/admin/usb/recovery/save")
def save():
    body = request.get_json(silent=True) or {}
    patch = {
        "verify": bool(body.get("verify", True)),
        "health_cmd": str(body.get("health_cmd") or ""),
        "allowed_seconds": int(body.get("allowed_seconds", 1200)),
        "require_mark": bool(body.get("require_mark", True)),
        "base_dir": str(body.get("base_dir") or ""),
        "only_trusted": bool(body.get("only_trusted", False)),
    }
    s = save_usb_recovery_settings(patch)
    return jsonify({"ok": True, "settings": s})

@bp_ur.post("/admin/usb/recovery/scan")
def scan():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    if not mount:
        return jsonify({"ok": False, "error": "no-mount"}), 400
    rep = scan_usb(mount)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

@bp_ur.post("/admin/usb/recovery/plan")
def plan():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    if not mount:
        return jsonify({"ok": False, "error": "no-mount"}), 400
    rep = plan_recover(mount, load_usb_recovery_settings())
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

@bp_ur.post("/admin/usb/recovery/apply")
def apply():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    health_cmd = str(body.get("health_cmd") or "")
    if not mount:
        return jsonify({"ok": False, "error": "no-mount"}), 400
    rep = apply_recover(mount, load_usb_recovery_settings(), health_cmd=health_cmd)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

def register_usb_recovery(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_ur)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("usb_recovery_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb/recovery")
        def _p(): return page()

        @pref.get("/admin/usb/recovery/status")
        def _s(): return status()

        @pref.post("/admin/usb/recovery/save")
        def _sv(): return save()

        @pref.post("/admin/usb/recovery/scan")
        def _sc(): return scan()

        @pref.post("/admin/usb/recovery/plan")
        def _pl(): return plan()

        @pref.post("/admin/usb/recovery/apply")
        def _ap(): return apply()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_ur)
    return app