# -*- coding: utf-8 -*-
"""routes/admin_registry.py - panel kataloga uzlov: svoya kartochka, spisok, deystviya.

Route:
  • GET /admin/registry - HTML
  • GET /admin/registry/status - {"self":cap,"nodes":[...]}
  • POST /admin/registry/publish_now - sobrat+sokhranit+eksport
  • POST /admin/registry/import_usb - prinuditelnyy import s USB
  • POST /admin/registry/suggest_targets - {job_type,args} -> targets dlya gibridnoy ocheredi

Mosty:
- Yavnyy (UX ↔ Inventarizatsiya): naglyadnyy obzor zheleza i knopki deystviy.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): JSON-otvety prigodny dlya avtomatizatsii.
- Skrytyy 2 (Praktika ↔ Sovmestimost): offlayn, stdlib; my ne menyaem yadro Ester.

Zemnoy abzats:
Eto “schit ucheta”: vidno, kto v seti i chto umeet, odnoy knopkoy - “obnovit tablichku” i podskazka gde sobirat.

# c=a+b"""
from __future__ import annotations
import os, json
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

from modules.registry.capabilities import build_capabilities  # type: ignore
from modules.registry.node_catalog import list_nodes, save_self_capabilities, import_from_usb  # type: ignore
from modules.portable.env import detect_portable_root  # type: ignore
from modules.hybrid.selector import suggest_targets  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_reg = Blueprint("admin_registry", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_reg.get("/admin/registry")
def page():
    return render_template("admin_registry.html", ab=AB)

@bp_reg.get("/admin/registry/status")
def status():
    self_cap = build_capabilities()
    nodes = list_nodes()
    return jsonify({"ok": True, "self": self_cap, "nodes": nodes})

@bp_reg.post("/admin/registry/publish_now")
def publish_now():
    cap = build_capabilities()
    res = save_self_capabilities(cap)
    exported = None
    usb = detect_portable_root(None)
    if usb and os.getenv("REGISTRY_USB_EXPORT","1") == "1":
        from modules.registry.node_catalog import export_to_usb  # type: ignore
        exported = export_to_usb(usb, cap)
    return jsonify({"ok": True, "save": res, "export": exported})

@bp_reg.post("/admin/registry/import_usb")
def import_usb():
    usb = detect_portable_root(None)
    if not usb:
        return jsonify({"ok": False, "error": "usb-not-found"}), 404
    res = import_from_usb(usb)
    return jsonify(res)

@bp_reg.post("/admin/registry/suggest_targets")
def api_suggest():
    body = request.get_json(silent=True) or {}
    jtype = (body.get("job_type") or "").strip()
    jargs = body.get("args") or {}
    return jsonify(suggest_targets(jtype, jargs))

def register_admin_registry(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_reg)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_registry_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/registry")
        def _p(): return page()

        @pref.get("/admin/registry/status")
        def _s(): return status()

        @pref.post("/admin/registry/publish_now")
        def _pub(): return publish_now()

        @pref.post("/admin/registry/import_usb")
        def _imp(): return import_usb()

        @pref.post("/admin/registry/suggest_targets")
        def _st(): return api_suggest()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_reg)
    return app