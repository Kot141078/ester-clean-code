# -*- coding: utf-8 -*-
"""
routes/social_upload_routes.py - REST: publikatsiya i status klyuchey.

Mosty:
- Yavnyy: (Veb ↔ Publikatsiya) odna ruchka initsiiruet upload (api|manual) i pishet zhurnal.
- Skrytyy #1: (RBAC ↔ Ostorozhnost) upload - tolko dlya operator|admin, esli vklyuchen RBAC.
- Skrytyy #2: (Profile ↔ Memory) modul uploaders uzhe pishet profile i ledzher.

Zemnoy abzats:
Eto knopka «Opublikovat»: s klyuchami - poydet v API; bez - dast idealnye instruktsii.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("social_upload_routes", __name__)

def register(app):
    app.register_blueprint(bp)

def _rbac_ok():
    if (os.getenv("SOCIAL_REQUIRE_RBAC","true").lower()=="false"): return True
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(["operator","admin"])
    except Exception:
        return True

try:
    from modules.social.uploaders import upload as _upload, creds_status as _creds  # type: ignore
except Exception:
    _upload=_creds=None  # type: ignore

@bp.route("/social/upload", methods=["POST"])
def api_upload():
    if _upload is None: return jsonify({"ok": False, "error":"upload_unavailable"}), 500
    if not _rbac_ok():  return jsonify({"ok": False, "error":"forbidden"}), 403
    d=request.get_json(True, True) or {}
    return jsonify(_upload(str(d.get("platform","youtube")), str(d.get("kit_dir",""))))

@bp.route("/social/creds/status", methods=["GET"])
def api_creds():
    if _creds is None: return jsonify({"ok": False, "error":"upload_unavailable"}), 500
    return jsonify(_creds())
# c=a+b