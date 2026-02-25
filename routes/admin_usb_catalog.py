# -*- coding: utf-8 -*-
"""routes/admin_usb_catalog.py - UI/API dlya Mini-Catalog na USB.

Route:
  • GET /admin/usb_catalog - stranitsa
  • GET /admin/usb_catalog/status - chtenie kataloga i whitelist
  • POST /admin/usb_catalog/preview - {selection:[uid], overrides:{uid:dest}} → plan
  • POST /admin/usb_catalog/import - primenit plan (AB=A → dry)

Mosty:
- Yavnyy (UX ↔ Import): from vybora elementov do otcheta o kopirovanii i alias'akh LM Studio.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): yavnyy plan s putyami i whitelist.
- Skrytyy 2 (Praktika ↔ Sovmestimost): offlayn, stdlib, AB-predokhranitel, yadro Ester ne trogaem.

Zemnoy abzats:
Eto “opis i razgruzka chemodana”: pokazyvaem, chto i kuda poydet, i po knopke perenosim.

# c=a+b"""
from __future__ import annotations
import os
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

from modules.usb_catalog.catalog import detect_usb_root, load_catalog, preview_import, apply_import  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_usb_catalog", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp.get("/admin/usb_catalog")
def page():
    if os.getenv("USB_CATALOG_ENABLE","1") != "1":
        return ("USB Catalog disabled", 403)
    return render_template("admin_usb_catalog.html", ab=AB)

@bp.get("/admin/usb_catalog/status")
def status():
    if os.getenv("USB_CATALOG_ENABLE","1") != "1":
        return jsonify({"ok": False, "error": "disabled"}), 403
    usb = detect_usb_root()
    if not usb:
        return jsonify({"ok": False, "error": "usb-not-found"}), 404
    cat = load_catalog(usb)
    wl = os.getenv("USB_RUNNER_DEST_WHITELIST","~/.ester/imports")
    return jsonify({"ok": True, "ab": AB, "usb": str(usb), "catalog": cat, "whitelist": wl})

@bp.post("/admin/usb_catalog/preview")
def preview():
    if os.getenv("USB_CATALOG_ENABLE","1") != "1":
        return jsonify({"ok": False, "error": "disabled"}), 403
    usb = detect_usb_root()
    if not usb:
        return jsonify({"ok": False, "error": "usb-not-found"}), 404
    body = request.get_json(silent=True) or {}
    sel = [str(x) for x in (body.get("selection") or [])]
    overrides = body.get("overrides") or {}
    plan = preview_import(usb, sel, overrides)
    return jsonify(plan)

@bp.post("/admin/usb_catalog/import")
def do_import():
    if os.getenv("USB_CATALOG_ENABLE","1") != "1":
        return jsonify({"ok": False, "error": "disabled"}), 403
    body = request.get_json(silent=True) or {}
    res = apply_import(body)
    return jsonify(res)

def register_admin_usb_catalog(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_usb_catalog_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb_catalog")
        def _p(): return page()

        @pref.get("/admin/usb_catalog/status")
        def _s(): return status()

        @pref.post("/admin/usb_catalog/preview")
        def _pr(): return preview()

        @pref.post("/admin/usb_catalog/import")
        def _im(): return do_import()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app