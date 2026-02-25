# -*- coding: utf-8 -*-
"""routes/usb_trust.py - UI/REST dlya Zero-Click USB: belyy spisok Re “zamok”.

Route:
  • GET /admin/usb/trust - HTML-pages
  • GET /admin/usb/trust/status - {settings, devices, probe:[]}
  • POST /admin/usb/trust/fingerprint - body {mount} v†' {ok,label,id,sha256,...}
  • POST /admin/usb/trust/add — body {mount, notes?} v†' addavlenie v whitelist
  • POST /admin/usb/trust/remove - body {id}
  • POST /admin/usb/trust/settings - body {zeroclick:bool, locked:bool, default_profile_id?:str}

Zemnoy abzats:
Odin ekran: “Proba tomov v†' dobavit doverennuyu fleshku v†' vklyuchit Zero-Click v†' (opts.) povesit zamok.”

Mosty:
- Yavnyy (Orkestratsiya v†" Vezopasnost): yavnyy kontrol whitelist Re globalnogo flaga.
- Skrytyy 1 (Infoteoriya v†" Prozrachnost): pokazyvaem otpechatok Re spisok ustroystv.
- Skrytyy 2 (Praktika v†" Ekspluatatsiya): nikakoy avtomaticheskoy zapisi bez yavnogo vklyucheniya.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from modules.usb.usb_probe import list_targets  # type: ignore
from modules.usb.usb_trust_store import settings as get_settings, update_settings, list_trusted, compute_fingerprint, trust_device, untrust  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_usb_trust = Blueprint("usb_trust", __name__)

@bp_usb_trust.get("/admin/usb/trust")
def page():
    return render_template("usb_trust.html")

@bp_usb_trust.get("/admin/usb/trust/status")
def api_status():
    return jsonify({"ok": True, "settings": get_settings(), "devices": list_trusted(), "probe": list_targets()})

@bp_usb_trust.post("/admin/usb/trust/fingerprint")
def api_fingerprint():
    data = request.get_json(silent=True) or {}
    mount = data.get("mount") or ""
    fp = compute_fingerprint(mount)
    return jsonify(fp)

@bp_usb_trust.post("/admin/usb/trust/add")
def api_add():
    data = request.get_json(silent=True) or {}
    mount = data.get("mount") or ""
    notes = data.get("notes") or ""
    fp = compute_fingerprint(mount)
    if not fp.get("ok"):
        return jsonify({"ok": False, "error": "manifest-not-found"}), 400
    item = trust_device({
        "id": fp["id"], "label": fp["label"], "serial": None, "fingerprint": fp["sha256"], "notes": notes
    })
    return jsonify({"ok": True, "item": item})

@bp_usb_trust.post("/admin/usb/trust/remove")
def api_remove():
    data = request.get_json(silent=True) or {}
    id_ = data.get("id") or ""
    ok = untrust(id_)
    return jsonify({"ok": bool(ok)}), (200 if ok else 404)

@bp_usb_trust.post("/admin/usb/trust/settings")
def api_settings():
    data = request.get_json(silent=True) or {}
    s = update_settings({
        "zeroclick": bool(data.get("zeroclick", False)),
        "locked": bool(data.get("locked", False)),
        "default_profile_id": (data.get("default_profile_id") or ""),
    })
    return jsonify({"ok": True, "settings": s})

def register_usb_trust(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_usb_trust)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("usb_trust_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb/trust")
        def _p():
            return page()

        @pref.get("/admin/usb/trust/status")
        def _ps():
            return api_status()

        @pref.post("/admin/usb/trust/fingerprint")
        def _pf():
            return api_fingerprint()

        @pref.post("/admin/usb/trust/add")
        def _pa():
            return api_add()

        @pref.post("/admin/usb/trust/remove")
        def _pr():
            return api_remove()

        @pref.post("/admin/usb/trust/settings")
        def _pt():
            return api_settings()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_usb_trust)
    return app