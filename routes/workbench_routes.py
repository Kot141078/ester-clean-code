# -*- coding: utf-8 -*-
"""
routes/workbench_routes.py - REST: skeffolding/zapis/listing koda.

Mosty:
- Yavnyy: (Veb ↔ Kod) predostavlyaet vneshnyuyu panel upravleniya masterskoy.
- Skrytyy #1: (RBAC ↔ Bezopasnost) zapis ogranichena rolyu admin.
- Skrytyy #2: (AutoDiscover ↔ Zhiznennyy tsikl) srazu gotov k registratsii moduley.

Zemnoy abzats:
Kak «panel v garazhe»: sozdaem fayl, dopisyvaem stroku, smotrim, chto u nas est.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("workbench_routes", __name__)

def register(app):
    app.register_blueprint(bp)

def _rbac_admin():
    if (os.getenv("RBAC_REQUIRED","true").lower()=="false"): return True
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(["admin"])
    except Exception:
        return True

try:
    from modules.workbench.code_ops import scaffold as _scf, write_file as _w, list_files as _ls  # type: ignore
except Exception:
    _scf=_w=_ls=None  # type: ignore

@bp.route("/workbench/scaffold", methods=["POST"])
def api_scaffold():
    if _scf is None: return jsonify({"ok": False, "error":"wb_unavailable"}), 500
    if not _rbac_admin(): return jsonify({"ok": False, "error":"forbidden"}), 403
    d=request.get_json(True, True) or {}
    return jsonify(_scf(str(d.get("kind","route")), str(d.get("package","routes.sample_hello")), str(d.get("name","sample_hello"))))

@bp.route("/workbench/write", methods=["POST"])
def api_write():
    if _w is None: return jsonify({"ok": False, "error":"wb_unavailable"}), 500
    if not _rbac_admin(): return jsonify({"ok": False, "error":"forbidden"}), 403
    d=request.get_json(True, True) or {}
    return jsonify(_w(str(d.get("path","")), str(d.get("content","")), str(d.get("mode","overwrite"))))

@bp.route("/workbench/list", methods=["GET"])
def api_list():
    if _ls is None: return jsonify({"ok": False, "error":"wb_unavailable"}), 500
    return jsonify(_ls())
# c=a+b