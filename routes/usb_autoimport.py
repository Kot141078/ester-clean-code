# -*- coding: utf-8 -*-
"""
routes/usb_autoimport.py - UI/REST dlya avto-importa s doverennoy fleshki.

Marshruty:
  • GET  /admin/usb/autoimport            - HTML
  • GET  /admin/usb/autoimport/status     - {env, stamps, enabled, interval}
  • POST /admin/usb/autoimport/scan       - prinuditelnyy odnokratnyy prokhod skanirovaniya

Mosty:
- Yavnyy (Kibernetika ↔ UX): odin ekran «vklyuchit, proverit, posmotret otchet».
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): pokazyvaem stamps i rezhim AB.
- Skrytyy 2 (Praktika ↔ Sovmestimost): ne trogaem mozg/pamyat - tolko nastroyki.

Zemnoy abzats:
Zdes vidno, vklyuchen li avtoimport, chto on sdelal v proshlyy raz, i mozhno «pnula» ruchnym skanom.

# c=a+b
"""
from __future__ import annotations

import json
import os
from flask import Blueprint, jsonify, render_template, request

from modules.usb.autoimport_settings import _load_stamps, _save_stamps, autoimport_from_mount  # type: ignore
from modules.usb.usb_probe import list_targets  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_usbai = Blueprint("usb_autoimport", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _enabled() -> bool:
    try:
        return bool(int(os.getenv("USB_AUTOIMPORT_ENABLE", "0")))
    except Exception:
        return False

def _interval() -> int:
    try:
        return max(3, int(os.getenv("USB_AUTOIMPORT_INTERVAL", "10")))
    except Exception:
        return 10

@bp_usbai.get("/admin/usb/autoimport")
def page():
    return render_template("usb_autoimport.html", ab=AB)

@bp_usbai.get("/admin/usb/autoimport/status")
def api_status():
    return jsonify({
        "ok": True,
        "ab": AB,
        "enabled": _enabled(),
        "interval": _interval(),
        "stamps": _load_stamps(),
        "env": {
            "USB_AUTOIMPORT_ENABLE": os.getenv("USB_AUTOIMPORT_ENABLE","0"),
            "USB_AUTOIMPORT_INTERVAL": os.getenv("USB_AUTOIMPORT_INTERVAL","10"),
            "USB_AUTOIMPORT_MODE": os.getenv("USB_AUTOIMPORT_MODE",""),
        },
        "targets": list_targets(),
    })

@bp_usbai.post("/admin/usb/autoimport/scan")
def api_scan():
    data = request.get_json(silent=True) or {}
    mount = (data.get("mount") or "").strip()
    if mount:
        rep = autoimport_from_mount(mount, ab_mode=AB)
        return jsonify({"ok": bool(rep.get("ok")), "result": rep})
    # esli ne ukazan mount - progon po vsem
    out = []
    for t in list_targets():
        m = t.get("mount") or ""
        if not m:
            continue
        r = autoimport_from_mount(m, ab_mode=AB)
        out.append({"mount": m, "result": r})
    return jsonify({"ok": True, "results": out})

def register_usb_autoimport(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_usbai)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("usb_autoimport_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb/autoimport")
        def _p(): return page()

        @pref.get("/admin/usb/autoimport/status")
        def _s(): return api_status()

        @pref.post("/admin/usb/autoimport/scan")
        def _sc(): return api_scan()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_usbai)
    return app