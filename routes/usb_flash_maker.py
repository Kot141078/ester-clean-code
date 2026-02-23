# -*- coding: utf-8 -*-
"""
routes/usb_flash_maker.py - UI/REST «Sborka fleshki Ester».

Marshruty:
  • GET  /admin/usb/make               - HTML
  • GET  /admin/usb/make/status        - tekuschie nastroyki + dostupnye toma
  • POST /admin/usb/make/save          - sokhranit nastroyki
  • GET  /admin/usb/make/probe         - spisok tomov
  • POST /admin/usb/make/plan          - plan po mount
  • POST /admin/usb/make/apply         - sobrat na mount

Mosty:
- Yavnyy (UX ↔ Offlayn-dostavka): v odnom meste - vybor fleshki, plan, sborka.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): raskrytye parametry i dry-run v AB=A.
- Skrytyy 2 (Praktika ↔ Sovmestimost): manifest 100% sovmestim s usb_zc_deploy.

Zemnoy abzats:
Eto «odna knopka bez golovnoy boli»: vybral fleshku - poluchil gotovuyu k dostavke kopiyu Ester.

# c=a+b
"""
from __future__ import annotations

import json, os
from flask import Blueprint, jsonify, render_template, request
from modules.usb.flash_maker_settings import load_flash_maker_settings, save_flash_maker_settings  # type: ignore
from modules.usb.flash_maker import list_targets, plan_make, apply_make  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_make = Blueprint("usb_flash_maker", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_make.get("/admin/usb/make")
def page():
    return render_template("usb_flash_maker.html", ab=AB)

@bp_make.get("/admin/usb/make/status")
def api_status():
    s = load_flash_maker_settings()
    return jsonify({"ok": True, "ab": AB, "settings": s, "targets": list_targets()})

@bp_make.post("/admin/usb/make/save")
def api_save():
    body = request.get_json(silent=True) or {}
    patch = {
        "include_models": bool(body.get("include_models", False)),
        "search_paths": list(body.get("search_paths") or []),
        "compression": (body.get("compression") or "zip"),
        "hashes": bool(body.get("hashes", True)),
        "label": str(body.get("label") or "Ester Portable"),
        "trust_mark": bool(body.get("trust_mark", True)),
        "window_s": int(body.get("window_s", 3600)),
        "base_dir": str(body.get("base_dir") or ""),
    }
    s = save_flash_maker_settings(patch)
    return jsonify({"ok": True, "settings": s})

@bp_make.get("/admin/usb/make/probe")
def api_probe():
    return jsonify({"ok": True, "targets": list_targets()})

@bp_make.post("/admin/usb/make/plan")
def api_plan():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    if not mount:
        return jsonify({"ok": False, "error": "no-mount"}), 400
    rep = plan_make(mount)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

@bp_make.post("/admin/usb/make/apply")
def api_apply():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    if not mount:
        return jsonify({"ok": False, "error": "no-mount"}), 400
    rep = apply_make(mount)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

def register_usb_flash_maker(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_make)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("usb_flash_maker_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb/make")
        def _p(): return page()

        @pref.get("/admin/usb/make/status")
        def _s(): return api_status()

        @pref.post("/admin/usb/make/save")
        def _sv(): return api_save()

        @pref.get("/admin/usb/make/probe")
        def _pr(): return api_probe()

        @pref.post("/admin/usb/make/plan")
        def _pl(): return api_plan()

        @pref.post("/admin/usb/make/apply")
        def _ap(): return api_apply()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_make)
    return app