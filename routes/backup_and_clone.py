# -*- coding: utf-8 -*-
"""
routes/backup_and_clone.py - UI/REST: bekap/vosstanovlenie nastroek + «fleshka-replika».

Marshruty:
  • GET  /admin/backup/legacy               - HTML
  • GET  /admin/backup/legacy/status        - predprosmotr bandla i spisok tomov
  • POST /admin/backup/legacy/export        - otdat JSON-bandl
  • POST /admin/backup/legacy/import        - prinyat JSON-bandl i primenit (merge|overwrite)
  • GET  /admin/backup/legacy/probe         - spisok semnykh tomov
  • POST /admin/backup/legacy/clone         - sozdat ESTER/ strukturu na vybrannom tome
  • POST /admin/backup/legacy/trust         - dobavit tom v whitelist Zero-Click

Mosty:
- Yavnyy (Ekspluatatsiya ↔ Bezopasnost): perenos whitelist/P2P bez ruchnoy rutiny.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): predprosmotr i detalnye otchety/plany.
- Skrytyy 2 (Praktika ↔ Sovmestimost): struktura ESTER/ sovmestima s Zero-Click/deploem.

Zemnoy abzats:
Odin ekran: «Snyat/Nalozhit nastroyki» i «Sobrat fleshku-repliku» - bez voprosov k polzovatelyu i bez syurprizov.

# c=a+b
"""
from __future__ import annotations

import json
import os
from flask import Blueprint, jsonify, render_template, request

from modules.selfmanage.backup_settings import export_bundle, import_bundle  # type: ignore
from modules.usb.usb_replicator import create_replica  # type: ignore
from modules.usb.usb_probe import list_targets  # type: ignore
from modules.usb.usb_trust_store import trust_device, compute_fingerprint  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_backup = Blueprint("backup_and_clone", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_backup.get("/admin/backup/legacy")
def page():
    return render_template("backup_and_clone.html", ab=AB)

@bp_backup.get("/admin/backup/legacy/status")
def api_status():
    bundle = export_bundle()
    return jsonify({"ok": True, "ab": AB, "bundle_preview": {"version": bundle.get("version"), "ts": bundle.get("ts"), "sizes": {
        "usb_trust": len(json.dumps(bundle.get("usb_trust", {}), ensure_ascii=False)),
        "p2p_settings": len(json.dumps(bundle.get("p2p_settings", {}), ensure_ascii=False)),
        "p2p_routing": len(json.dumps(bundle.get("p2p_routing", {}), ensure_ascii=False)),
    }}})

@bp_backup.post("/admin/backup/legacy/export")
def api_export():
    bundle = export_bundle()
    return jsonify({"ok": True, "bundle": bundle})

@bp_backup.post("/admin/backup/legacy/import")
def api_import():
    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "merge").lower()
    try:
        bundle = data.get("bundle")
        if isinstance(bundle, str):
            bundle = json.loads(bundle)
        rep = import_bundle(bundle or {}, mode=mode, dry=(AB != "B"))
        return jsonify({"ok": rep.get("ok", False), "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@bp_backup.get("/admin/backup/legacy/probe")
def api_probe():
    return jsonify({"ok": True, "targets": list_targets()})

@bp_backup.post("/admin/backup/legacy/clone")
def api_clone():
    data = request.get_json(silent=True) or {}
    mount = data.get("mount") or ""
    label = data.get("label") or None
    bundle = export_bundle()
    rep = create_replica(mount, bundle=bundle, label=label, dry=(AB != "B"))
    return jsonify({"ok": rep.get("ok", False), "result": rep})

@bp_backup.post("/admin/backup/legacy/trust")
def api_trust():
    data = request.get_json(silent=True) or {}
    mount = data.get("mount") or ""
    fp = compute_fingerprint(mount)
    if not fp.get("ok"):
        return jsonify({"ok": False, "error": "manifest-not-found"}), 400
    item = trust_device({"id": fp["id"], "label": fp.get("label") or "ESTER", "serial": None, "fingerprint": fp["sha256"], "notes": "replica"})
    return jsonify({"ok": True, "item": item})

def register_backup_and_clone(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_backup)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("backup_and_clone_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/backup/legacy")
        def _p(): return page()

        @pref.get("/admin/backup/legacy/status")
        def _ps(): return api_status()

        @pref.post("/admin/backup/legacy/export")
        def _ex(): return api_export()

        @pref.post("/admin/backup/legacy/import")
        def _im(): return api_import()

        @pref.get("/admin/backup/legacy/probe")
        def _pr(): return api_probe()

        @pref.post("/admin/backup/legacy/clone")
        def _cl(): return api_clone()

        @pref.post("/admin/backup/legacy/trust")
        def _tr(): return api_trust()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_backup)
    return app
