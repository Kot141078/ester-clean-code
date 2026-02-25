# -*- coding: utf-8 -*-
"""routes/admin_usb_boot.py - UI/REST dlya sozdaniya USB-nositelya s autorun-planom project.

Route:
  • GET /admin/usb_boot - HTML
  • POST /admin/usb_boot/make - {mount, project_dir, layout?, publish_on_target?, include_runner?}

Mosty:
- Yavnyy (UX ↔ Avtomatizatsiya): odna knopka - gotovaya fleshka, kotoruyu tselevoy uzel poymet sam.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): otvet - chitaemyy JSON (plan, puti), dry v A.
- Skrytyy 2 (Praktika ↔ Sovmestimost): stdlib, uvazhaem limity i AB, bez vneshnikh zavisimostey.

Zemnoy abzats:
Eto “master zapisi”: formiruet na fleshke ponyatnuyu strukturu i stsenariy dlya tselevogo uzla.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.usb.bootstrap import make_project_usb  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_usb = Blueprint("admin_usb_boot", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_usb.get("/admin/usb_boot")
def page():
    return render_template("admin_usb_boot.html", ab=AB)

@bp_usb.post("/admin/usb_boot/make")
def make():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    proj  = (body.get("project_dir") or "").strip()
    layout = (body.get("layout") or "files").strip()
    publish = bool(body.get("publish_on_target", True))
    include_runner = bool(body.get("include_runner", True))
    if not mount or not proj:
        return jsonify({"ok": False, "error": "mount and project_dir required"}), 400
    return jsonify(make_project_usb(mount, proj, layout=layout, publish_on_target=publish, include_runner=include_runner))

def register_admin_usb_boot(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_usb)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_usb_boot_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb_boot")
        def _p(): return page()

        @pref.post("/admin/usb_boot/make")
        def _m(): return make()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_usb)
    return app