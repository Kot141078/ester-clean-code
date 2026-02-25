# -*- coding: utf-8 -*-
"""routes/selfevo_routes.py - REST: kuznitsa samoevolyutsii (dryrun/apply/list) s RBAC i "pilyuley".

Mosty:
- Yavnyy: (Veb ↔ FS) sozdaem bezopasno novye artefakty koda.
- Skrytyy #1: (Profile ↔ Audit) fiksiruem izmeneniya s kheshami.
- Skrytyy #2: (Registratsiya ↔ Zhiznennyy tsikl) po flagu podklyuchaem modul srazu.

Zemnoy abzats:
Ofitsialnaya “door v masterskuyu”: bez razresheniya - tolko posmotret, s razresheniem i podtverzhdeniem - akkuratno primenit.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("selfevo_routes", __name__)

def register(app):
    app.register_blueprint(bp)

def _rbac_ok():
    if (os.getenv("RBAC_REQUIRED","true").lower()=="false"): return True
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(["admin"])
    except Exception:
        return True

try:
    from modules.selfevo.forge import dryrun as _dry, apply as _apply, list_items as _list  # type: ignore
except Exception:
    _dry=_apply=_list=None  # type: ignore

@bp.route("/selfevo/forge/dryrun", methods=["POST"])
def api_dry():
    if _dry is None: return jsonify({"ok": False, "error":"selfevo_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_dry(str(d.get("path","")), str(d.get("kind","route")), str(d.get("name","new_module")), str(d.get("desc","")), str(d.get("export","routes"))))

@bp.route("/selfevo/forge/apply", methods=["POST"])
def api_apply():
    if _apply is None: return jsonify({"ok": False, "error":"selfevo_unavailable"}), 500
    if not _rbac_ok(): return jsonify({"ok": False, "error":"forbidden"}), 403
    if os.getenv("SELF_EVO_ALLOW_WRITE","false").lower()!="true":
        return jsonify({"ok": False, "error":"write_forbidden_env"}), 400
    if request.headers.get("X-Change-Approval","").lower()!="yes":
        return jsonify({"ok": False, "error":"pill_required"}), 428
    d=request.get_json(True, True) or {}
    return jsonify(_apply(str(d.get("path","")), str(d.get("code","")) or _dry(d.get("path",""), d.get("kind","route"), d.get("name","new_module"), d.get("desc",""), d.get("export","routes"))["code"], bool(d.get("register_after",False))))

@bp.route("/selfevo/forge/list", methods=["GET"])
def api_list():
    if _list is None: return jsonify({"ok": False, "error":"selfevo_unavailable"}), 500
    return jsonify(_list())
# c=a+b