# -*- coding: utf-8 -*-
"""routes/admin_portable_checklist.py - integratsionnyy check-list (vetka B):
  • /admin/portable/checklist - stranitsa
  • /admin/portable/checklist/status - USB struktura, lock-prevyu, ocheredi, katalogi, LAN-svodka
  • /admin/portable/lock_write - zapisat ESTER/manifest_lock.json (AB=A → dry)
  • /admin/portable/installer_seed - zapisat ESTER/installer/* (AB=A → dry)
  • /admin/portable/compat_check - bazovaya proverka sovmestimosti s ester_manifest.json

Mosty:
- Yavnyy (Ekspluatatsiya ↔ Priemka): vse klyuchevoe v odnom meste: struktura nositelya, lock i installer.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): edinyy JSON-status bez skrytykh pobochek.
- Skrytyy 2 (Praktika ↔ Sovmestimost): dry AB, offlayn, proverki ne trogayut myshlenie/pamyat/volyu Ester.

Zemnoy abzats:
This is “list priemki”: odin ekran pered vydachey/kopirovaniem - vse zelenoe/zheltoe/krasnoe vidno srazu.

# c=a+b"""
from __future__ import annotations
import os, json
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

AB = (os.getenv("AB_MODE") or "A").strip().upper()

from modules.portable.checks import (  # type: ignore
    detect_usb_root, required_usb_dirs, default_lock_filelist,
    build_lock, write_lock, seed_installer, load_json, compat_check
)
from modules.usb_runner.jobs import list_jobs  # type: ignore
from modules.usb_catalog.catalog import load_catalog  # type: ignore
from modules.lan_catalog.peers import list_peers, load_catalogs  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_portable_checklist", __name__)

@bp.get("/admin/portable/checklist")
def page():
    if os.getenv("PORTABLE_CHECKLIST_ENABLE","1") != "1":
        return ("Checklist disabled", 403)
    return render_template("admin_portable_checklist.html", ab=AB)

@bp.get("/admin/portable/checklist/status")
def status():
    if os.getenv("PORTABLE_CHECKLIST_ENABLE","1") != "1":
        return jsonify({"ok": False, "error": "disabled"}), 403
    usb = detect_usb_root()
    usb_info = (required_usb_dirs(usb) if usb else {"ester": None, "exists": {}, "paths": {}})
    filelist = default_lock_filelist()
    lock = build_lock(filelist)
    # ocheredi/katalogi
    jobs = (list_jobs(usb, 1000) if usb else {"items": []})
    cat  = (load_catalog(usb) if usb else {"items": []})
    peers = list_peers()
    lan_items = load_catalogs()
    # vozmozhnyy damp na USB
    manifest = {}
    if usb:
        compat_json_path = Path(usb) / "ESTER" / "compat" / "ester_manifest.json"
        if compat_json_path.exists():
            manifest = load_json(compat_json_path)
    return jsonify({
        "ok": True, "ab": AB,
        "usb": (str(usb) if usb else None),
        "usb_info": usb_info,
        "lock_preview": lock,
        "jobs_queue": len(jobs.get("items") or []),
        "catalog_items": len(cat.get("items") or []),
        "lan_peers": len(peers.get("peers") or []),
        "lan_items": len(lan_items.get("items") or []),
        "compat_manifest_presence": bool(manifest)
    })

@bp.post("/admin/portable/lock_write")
def lock_write():
    usb = detect_usb_root()
    if not usb:
        return jsonify({"ok": False, "error": "usb-not-found"}), 404
    body = request.get_json(silent=True) or {}
    fl = body.get("files") or []
    filelist = [Path(p) for p in fl] if fl else default_lock_filelist()
    lock = build_lock(filelist)
    res = write_lock(usb, lock)
    return jsonify({"ok": True, "result": res, "lock": lock})

@bp.post("/admin/portable/installer_seed")
def installer_seed():
    usb = detect_usb_root()
    if not usb:
        return jsonify({"ok": False, "error": "usb-not-found"}), 404
    res = seed_installer(usb)
    return jsonify({"ok": True, "result": res})

@bp.post("/admin/portable/compat_check")
def compat_check_api():
    body = request.get_json(silent=True) or {}
    manifest = body.get("manifest") or {}
    # attempt to pick up from USB, if not transmitted
    if not manifest:
        usb = detect_usb_root()
        if usb:
            p = Path(usb) / "ESTER" / "compat" / "ester_manifest.json"
            if p.exists():
                try:
                    manifest = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    manifest = {}
    res = compat_check(manifest if isinstance(manifest, dict) else {})
    return jsonify({"ok": True, "result": res})

def register_admin_portable_checklist(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_portable_checklist_pref", __name__, url_prefix=url_prefix)
        @pref.get("/admin/portable/checklist")
        def _p(): return page()
        @pref.get("/admin/portable/checklist/status")
        def _s(): return status()
        @pref.post("/admin/portable/lock_write")
        def _lw(): return lock_write()
        @pref.post("/admin/portable/installer_seed")
        def _is(): return installer_seed()
        @pref.post("/admin/portable/compat_check")
        def _cc(): return compat_check_api()
        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app