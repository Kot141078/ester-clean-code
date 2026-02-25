# -*- coding: utf-8 -*-
"""routes/usb_profiles.py - upravlenie profilyami (UI/REST).

Route:
  • GET /admin/usb/profiles - HTML-stranitsa
  • GET /admin/usb/profiles/list - spisok profiley
  • GET /admin/usb/profiles/get?id=… – profil
  • POST /admin/usb/profiles/save - sozdat/obnovit
  • POST /admin/usb/profiles/delete - delete
  • GET /admin/usb/profiles/export?id=… - eksport (JSON)
  • POST /admin/usb/profiles/import - import (JSON)

Mosty:
- Yavnyy (Kibernetika v†" UX): "sokhrani Re pereispolzuy" konfiguratsii sborki.
- Skrytyy 1 (Infoteoriya v†" Minimalizm): REST na prostom JSON, bez skrytykh said-effektov.
- Skrytyy 2 (Praktika v†" Vezopasnost): ni klyuchey/sekretov — tolko parametry upakovki.

Zemnoy abzats:
Profile - kak meditsinskaya karta patsienta: po ney bystro gotovim “nabor” dlya operatsii (sborki USB).

# c=a+b"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from flask import Blueprint, jsonify, render_template, request

from modules.selfmanage.usb_profiles import list_profiles, get_profile, upsert_profile, delete_profile, export_profile, import_profile  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_usb_profiles = Blueprint("usb_profiles", __name__)

@bp_usb_profiles.get("/admin/usb/profiles")
def page_profiles():
    return render_template("usb_profiles.html")

@bp_usb_profiles.get("/admin/usb/profiles/list")
def api_list():
    return jsonify({"ok": True, "items": list_profiles()})

@bp_usb_profiles.get("/admin/usb/profiles/get")
def api_get():
    pid = (request.args.get("id") or "").strip()
    p = get_profile(pid) if pid else None
    if not p:
        return jsonify({"ok": False, "error": "not-found"}), 404
    return jsonify({"ok": True, "item": p})

@bp_usb_profiles.post("/admin/usb/profiles/save")
def api_save():
    is_json = request.is_json
    data: Dict[str, Any]
    if is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = {
            "id": (request.form.get("id") or "").strip() or None,
            "name": (request.form.get("name") or "").strip(),
            "label": (request.form.get("label") or "").strip(),
            "with_release": request.form.get("with_release") in ("1", "true", "True"),
            "include_state": request.form.get("include_state") in ("1", "true", "True"),
            "dump_paths": [x.strip() for x in (request.form.get("dump_paths") or "").split(",") if x.strip()],
            "notes": (request.form.get("notes") or "").strip(),
        }
    saved = upsert_profile(data)
    return jsonify({"ok": True, "item": saved})

@bp_usb_profiles.post("/admin/usb/profiles/delete")
def api_delete():
    pid = (request.form.get("id") if not request.is_json else (request.get_json(silent=True) or {}).get("id")) or ""
    if not pid:
        return jsonify({"ok": False, "error": "id-required"}), 400
    ok = delete_profile(str(pid))
    return jsonify({"ok": bool(ok)}), (200 if ok else 404)

@bp_usb_profiles.get("/admin/usb/profiles/export")
def api_export():
    pid = (request.args.get("id") or "").strip()
    obj = export_profile(pid) if pid else None
    if not obj:
        return jsonify({"ok": False, "error": "not-found"}), 404
    # Bozvraschaem sam JSON (copy-paste friendly)
    return jsonify({"ok": True, "profile": obj})

@bp_usb_profiles.post("/admin/usb/profiles/import")
def api_import():
    is_json = request.is_json
    try:
        obj = request.get_json(silent=True) if is_json else json.loads(request.form.get("json") or "{}")
    except Exception:
        return jsonify({"ok": False, "error": "bad-json"}), 400
    saved = import_profile(obj or {})
    return jsonify({"ok": True, "item": saved})

def register_usb_profiles(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_usb_profiles)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("usb_profiles_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb/profiles")
        def _p():
            return page_profiles()

        @pref.get("/admin/usb/profiles/list")
        def _pl():
            return api_list()

        @pref.get("/admin/usb/profiles/get")
        def _pg():
            return api_get()

        @pref.post("/admin/usb/profiles/save")
        def _ps():
            return api_save()

        @pref.post("/admin/usb/profiles/delete")
        def _pd():
            return api_delete()

        @pref.get("/admin/usb/profiles/export")
        def _pe():
            return api_export()

        @pref.post("/admin/usb/profiles/import")
        def _pi():
            return api_import()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_usb_profiles)
    return app