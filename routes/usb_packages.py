# -*- coding: utf-8 -*-
"""routes/usb_packages.py - UI/REST dlya USB-packetov (sborka, skan, proverka, import).

Route:
  • GET /admin/packages - HTML
  • GET /admin/packages/status - spisok proektov/sessiy/tomov + naydennye pakety
  • POST /admin/packages/plan - plan vklyucheniya
  • POST /admin/packages/build - sobrat ZIP (i opts. skopirovat na USB)
  • POST /admin/packages/scan - nayti pakety na USB
  • POST /admin/packages/verify - proverit ZIP
  • POST /admin/packages/import - importirovat ZIP (mode=merge|skip)

Mosty:
- Yavnyy (UX ↔ Audit): prozrachnyy tsikl “soberi→prover→importiruy”.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): SHA-256 i zhurnal priemki v odnom meste.
- Skrytyy 2 (Praktika ↔ Sovmestimost): offlayn, flat ZIP/JSON, drop-in.

Zemnoy abzats:
This is “upakovochnyy stol”: sobrali paket, proverili plomby, otpravili or prinyali - bez boli.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.projects.project_store import list_projects  # type: ignore
from modules.prompts.storage import list_sessions  # type: ignore
from modules.usb.recovery import list_usb_targets  # type: ignore
from modules.pack.packager import plan_package, build_package, scan_usb_packages, verify_package, import_package  # type: ignore
from modules.pack.accept_log import read_tail  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_pkg = Blueprint("usb_packages", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_pkg.get("/admin/packages")
def page():
    return render_template("usb_packages.html", ab=AB)

@bp_pkg.get("/admin/packages/status")
def status():
    projs = list_projects()
    sess = list_sessions()
    usb = list_usb_targets()
    # avto-skan
    mounts = [i.get("mount") for i in (usb or []) if i.get("mount")]
    found = scan_usb_packages(mounts)
    return jsonify({"ok": True, "ab": AB, "projects": projs, "sessions": sess, "usb": usb, "found": found, "log": read_tail(50)})

@bp_pkg.post("/admin/packages/plan")
def plan():
    body = request.get_json(silent=True) or {}
    spec = {"projects": body.get("projects", []), "sessions": body.get("sessions", []), "resources": bool(body.get("resources", False))}
    return jsonify(plan_package(spec))

@bp_pkg.post("/admin/packages/build")
def build():
    body = request.get_json(silent=True) or {}
    spec = {"projects": body.get("projects", []), "sessions": body.get("sessions", []), "resources": bool(body.get("resources", False))}
    mount = (body.get("mount") or "").strip() or None
    rep = build_package(spec, mount=mount)
    return jsonify(rep)

@bp_pkg.post("/admin/packages/scan")
def scan():
    body = request.get_json(silent=True) or {}
    mounts = body.get("mounts") or [i.get("mount") for i in (list_usb_targets() or []) if i.get("mount")]
    return jsonify(scan_usb_packages(mounts))

@bp_pkg.post("/admin/packages/verify")
def verify():
    body = request.get_json(silent=True) or {}
    path = (body.get("path") or "").strip()
    if not path: return jsonify({"ok": False, "error": "path required"}), 400
    return jsonify(verify_package(path))

@bp_pkg.post("/admin/packages/import")
def imp():
    body = request.get_json(silent=True) or {}
    path = (body.get("path") or "").strip()
    mode = (body.get("mode") or "merge").strip()
    if not path: return jsonify({"ok": False, "error": "path required"}), 400
    return jsonify(import_package(path, mode=mode))

def register_usb_packages(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_pkg)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("usb_packages_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/packages")
        def _p(): return page()

        @pref.get("/admin/packages/status")
        def _s(): return status()

        @pref.post("/admin/packages/plan")
        def _pl(): return plan()

        @pref.post("/admin/packages/build")
        def _b(): return build()

        @pref.post("/admin/packages/scan")
        def _sc(): return scan()

        @pref.post("/admin/packages/verify")
        def _v(): return verify()

        @pref.post("/admin/packages/import")
        def _i(): return imp()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_pkg)
    return app