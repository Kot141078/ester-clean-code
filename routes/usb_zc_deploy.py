# -*- coding: utf-8 -*-
"""
routes/usb_zc_deploy.py - UI/REST dlya Zero-Click USB Deploy.

Marshruty:
  • GET  /admin/usb/zc-deploy            - HTML
  • GET  /admin/usb/zc-deploy/status     - sostoyanie slotov/shtampov/nastroek
  • GET  /admin/usb/zc-deploy/probe      - spisok tomov
  • POST /admin/usb/zc-deploy/plan       - plan po mount
  • POST /admin/usb/zc-deploy/apply      - primenit po mount
  • POST /admin/usb/zc-deploy/save       - sokhranit nastroyki (enable/interval/base_dir/health_cmd)

Mosty:
- Yavnyy (Kibernetika ↔ UX): odin ekran dlya bezopasnogo «perelivaniya» relizov s doverennoy fleshki.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): pokazyvaem sloty, tekuschuyu versiyu i shtampy.
- Skrytyy 2 (Praktika ↔ Sovmestimost): dry-run v A i realnoe primenenie v B.

Zemnoy abzats:
Zdes - knopki «Plan» i «Primenit»; sleva fleshka, sprava sloty. Spokoyno i bez syurprizov.

# c=a+b
"""
from __future__ import annotations

import json, os
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

from modules.usb.zc_deploy_settings import load_settings, save_settings  # type: ignore
from modules.usb.usb_probe import list_targets  # type: ignore
from modules.usb.zc_deploy import plan_from_mount, apply_from_mount  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_zc = Blueprint("usb_zc_deploy", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
STAMPS = STATE_DIR / "zc_deploy_stamps.json"

def _read_json(p: Path):
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

@bp_zc.get("/admin/usb/zc-deploy")
def page():
    return render_template("usb_zc_deploy.html", ab=AB)

@bp_zc.get("/admin/usb/zc-deploy/status")
def api_status():
    s = load_settings()
    st = _read_json(STAMPS)
    base = Path(os.path.expanduser(s["base_dir"]))
    slots = {
        "base": str(base),
        "slotA": str(base / "slotA"),
        "slotB": str(base / "slotB"),
        "current": str((base / "current").resolve()) if (base / "current").exists() else None
    }
    return jsonify({"ok": True, "ab": AB, "settings": s, "stamps": st, "slots": slots})

@bp_zc.get("/admin/usb/zc-deploy/probe")
def api_probe():
    return jsonify({"ok": True, "targets": list_targets()})

@bp_zc.post("/admin/usb/zc-deploy/plan")
def api_plan():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    if not mount:
        return jsonify({"ok": False, "error": "no-mount"}), 400
    s = load_settings()
    rep = plan_from_mount(mount, s["base_dir"], ab_mode=AB)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

@bp_zc.post("/admin/usb/zc-deploy/apply")
def api_apply():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    if not mount:
        return jsonify({"ok": False, "error": "no-mount"}), 400
    s = load_settings()
    rep = apply_from_mount(mount, s["base_dir"], ab_mode=AB, health_cmd=s.get("health_cmd",""))
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

@bp_zc.post("/admin/usb/zc-deploy/save")
def api_save():
    body = request.get_json(silent=True) or {}
    s = save_settings({
        "enable": bool(body.get("enable", False)),
        "interval": max(3, int(body.get("interval", 10))),
        "base_dir": str(body.get("base_dir") or ""),
        "health_cmd": str(body.get("health_cmd") or ""),
    })
    return jsonify({"ok": True, "settings": s})

def register_usb_zc_deploy(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_zc)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("usb_zc_deploy_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb/zc-deploy")
        def _p(): return page()

        @pref.get("/admin/usb/zc-deploy/status")
        def _s(): return api_status()

        @pref.get("/admin/usb/zc-deploy/probe")
        def _pr(): return api_probe()

        @pref.post("/admin/usb/zc-deploy/plan")
        def _pl(): return api_plan()

        @pref.post("/admin/usb/zc-deploy/apply")
        def _ap(): return api_apply()

        @pref.post("/admin/usb/zc-deploy/save")
        def _sv(): return api_save()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_zc)
    return app