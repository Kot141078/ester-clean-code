# -*- coding: utf-8 -*-
"""
routes/sync_profiles.py — UI/REST dlya profiley sinkhronizatsii.

Marshruty:
  • GET  /admin/sync-profiles
  • GET  /admin/sync-profiles/list
  • GET  /admin/sync-profiles/get?id=...
  • POST /admin/sync-profiles/save
  • POST /admin/sync-profiles/delete
  • GET  /admin/sync-profiles/export?id=...
  • POST /admin/sync-profiles/import

Mosty:
- Yavnyy (Kibernetika v†" UX): odin ekran upravlyaet skhemami raskladki dannykh.
- Skrytyy 1 (Infoteoriya v†" Kontrakty): chistyy JSON, drop-in dlya ostalnykh moduley.
- Skrytyy 2 (Praktika v†" Vezopasnost): net setevykh pobochnykh effektov.

Zemnoy abzats:
Eto katalog «skhem skladirovaniya» — chtoby komanda ne sporila, kuda klast.

# c=a+b
"""
from __future__ import annotations

import json
from typing import Any, Dict

from flask import Blueprint, jsonify, render_template, request

from modules.selfmanage.sync_profiles import list_profiles, get_profile, upsert_profile, delete_profile, export_profile, import_profile  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_sync_profiles = Blueprint("sync_profiles", __name__)

@bp_sync_profiles.get("/admin/sync-profiles")
def page_profiles():
    return render_template("sync_profiles.html")

@bp_sync_profiles.get("/admin/sync-profiles/list")
def api_list():
    return jsonify({"ok": True, "items": list_profiles()})

@bp_sync_profiles.get("/admin/sync-profiles/get")
def api_get():
    pid = (request.args.get("id") or "").strip()
    p = get_profile(pid) if pid else None
    if not p:
        return jsonify({"ok": False, "error": "not-found"}), 404
    return jsonify({"ok": True, "item": p})

@bp_sync_profiles.post("/admin/sync-profiles/save")
def api_save():
    if request.is_json:
        data: Dict[str, Any] = request.get_json(silent=True) or {}
    else:
        data = {
            "id": (request.form.get("id") or "").strip() or None,
            "name": (request.form.get("name") or "").strip(),
            "release_dest": (request.form.get("release_dest") or "").strip(),
            "dump_dest": (request.form.get("dump_dest") or "").strip(),
            "notes": (request.form.get("notes") or "").strip(),
        }
    saved = upsert_profile(data)
    return jsonify({"ok": True, "item": saved})

@bp_sync_profiles.post("/admin/sync-profiles/delete")
def api_delete():
    pid = (request.form.get("id") if not request.is_json else (request.get_json(silent=True) or {}).get("id")) or ""
    if not pid:
        return jsonify({"ok": False, "error": "id-required"}), 400
    ok = delete_profile(str(pid))
    return jsonify({"ok": bool(ok)}), (200 if ok else 404)

@bp_sync_profiles.get("/admin/sync-profiles/export")
def api_export():
    pid = (request.args.get("id") or "").strip()
    obj = export_profile(pid) if pid else None
    if not obj:
        return jsonify({"ok": False, "error": "not-found"}), 404
    return jsonify({"ok": True, "profile": obj})

@bp_sync_profiles.post("/admin/sync-profiles/import")
def api_import():
    try:
        obj = request.get_json(silent=True) if request.is_json else json.loads(request.form.get("json") or "{}")
    except Exception:
        return jsonify({"ok": False, "error": "bad-json"}), 400
    saved = import_profile(obj or {})
    return jsonify({"ok": True, "item": saved})

def register_sync_profiles(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_sync_profiles)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("sync_profiles_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/sync-profiles")
        def _p():
            return page_profiles()

        @pref.get("/admin/sync-profiles/list")
        def _pl():
            return api_list()

        @pref.get("/admin/sync-profiles/get")
        def _pg():
            return api_get()

        @pref.post("/admin/sync-profiles/save")
        def _ps():
            return api_save()

        @pref.post("/admin/sync-profiles/delete")
        def _pd():
            return api_delete()

        @pref.get("/admin/sync-profiles/export")
        def _pe():
            return api_export()

        @pref.post("/admin/sync-profiles/import")
        def _pi():
            return api_import()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_sync_profiles)
    return app