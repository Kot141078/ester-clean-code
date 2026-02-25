# -*- coding: utf-8 -*-
"""routes/usb_deploy.py - UI/REST dlya Zero-Click USB Deploy.

Route:
  • GET /admin/usb/deploy - HTML
  • GET /admin/usb/deploy/status - {env, settings, stamps, targets, last_log_head}
  • POST /admin/usb/deploy/scan - scan_and_apply_all() (AB soblyudaetsya)
  • POST /admin/usb/deploy/plan - plan_deploy(mount)
  • POST /admin/usb/deploy/apply - apply_deploy(mount)

Mosty:
- Yavnyy (Nablyudaemost ↔ Ekspluatatsiya): odin ekran dlya kontrolya zero-click deploya.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): shtampy/logi vidny; AB-rezhim otrazhen.
- Skrytyy 2 (Praktika ↔ Sovmestimost): bez vmeshatelstva v yadro; only instrument deployment.

Zemnoy abzats:
Zdes vidno, chto budet sdelano pri vstavke fleshki, i mozhno vruchnuyu “pnula” skan or primenit deploy s vybrannogo toma.

# c=a+b"""
from __future__ import annotations

import json, os
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

from modules.usb.usb_deploy_settings import load_deploy_settings, save_deploy_settings  # type: ignore
from modules.usb.usb_deploy import plan_deploy, apply_deploy, scan_and_apply_all  # type: ignore
from modules.usb.usb_probe import list_targets  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ud = Blueprint("usb_deploy", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
STAMPS = STATE_DIR / "usb_deploy_stamps.json"
LOG = STATE_DIR / "usb_deploy_log.jsonl"

def _load_json(p: Path):
    try:
        if p.exists(): return json.loads(p.read_text(encoding="utf-8"))
    except Exception: pass
    return {}

def _tail_log(n: int = 50):
    try:
        if not LOG.exists(): return []
        lines = LOG.read_text(encoding="utf-8").splitlines()
        return [json.loads(x) for x in lines[-n:]]
    except Exception:
        return []

@bp_ud.get("/admin/usb/deploy")
def page():
    return render_template("usb_deploy.html", ab=AB)

@bp_ud.get("/admin/usb/deploy/status")
def api_status():
    s = load_deploy_settings()
    return jsonify({
        "ok": True, "ab": AB,
        "settings": s,
        "env": {
            "USB_DEPLOY_ENABLE": os.getenv("USB_DEPLOY_ENABLE","0"),
            "USB_DEPLOY_INTERVAL": os.getenv("USB_DEPLOY_INTERVAL",""),
            "USB_DEPLOY_BASE_DIR": os.getenv("USB_DEPLOY_BASE_DIR",""),
            "USB_DEPLOY_STAGING": os.getenv("USB_DEPLOY_STAGING",""),
            "USB_DEPLOY_ALLOW_OVERWRITE": os.getenv("USB_DEPLOY_ALLOW_OVERWRITE",""),
            "USB_DEPLOY_CHECKSUMS": os.getenv("USB_DEPLOY_CHECKSUMS",""),
        },
        "stamps": _load_json(STAMPS),
        "targets": list_targets(),
        "last_log_head": _tail_log(30),
    })

@bp_ud.post("/admin/usb/deploy/scan")
def api_scan():
    rep = scan_and_apply_all(ab_mode=AB)
    return jsonify({"ok": True, "results": rep})

@bp_ud.post("/admin/usb/deploy/plan")
def api_plan():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    if not mount: return jsonify({"ok": False, "error": "no-mount"}), 400
    rep = plan_deploy(mount, ab_mode=AB)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

@bp_ud.post("/admin/usb/deploy/apply")
def api_apply():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    if not mount: return jsonify({"ok": False, "error": "no-mount"}), 400
    rep = apply_deploy(mount, ab_mode=AB)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

def register_usb_deploy(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_ud)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("usb_deploy_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb/deploy")
        def _p(): return page()

        @pref.get("/admin/usb/deploy/status")
        def _s(): return api_status()

        @pref.post("/admin/usb/deploy/scan")
        def _sc(): return api_scan()

        @pref.post("/admin/usb/deploy/plan")
        def _pl(): return api_plan()

        @pref.post("/admin/usb/deploy/apply")
        def _ap(): return api_apply()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_ud)
    return app