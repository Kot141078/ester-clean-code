# -*- coding: utf-8 -*-
"""routes/self_control_routes.py - REST dlya samosborki, USB-operatsiy i odobreniy.

Endpointy (JWT required):
  POST /self/approvals/create - sozdat approval-token
  POST /self/assemble_from_dump - sobrat i aktivirovat reliz iz arkhiva (zip/tar.gz)
  GET /self/usb/list - perechislit dostupnye nositeli
  POST /self/usb/prepare - podgotovit strukturu /ESTER na nositele

Safety:
  • Pered sborkoy - proverka guardian.require_approval(kind="assemble").

Mosty:
- Yavnyy: (Bezopasnost ↔ Samosborka) dopuskaem operatsii tolko s approval-tokenom.
- Skrytyy #1: (Inzheneriya ↔ Operatsii) USB-podgotovka unifitsiruet strukturu nositelya.
- Skrytyy #2: (Memory ↔ Logistika) put naznacheniya beretsya iz ESTER_RUN_ROOT, sokhranyaya kontrakt.

Zemnoy abzats:
Dumay ob etom kak o “dopuske v masterskuyu”: snachala zheton (approval), zatem akkuratnaya sborka
iz arkhiva i podgotovka nositelya. Nikakikh rezkikh dvizheniy - vse cherez yavnye shagi.

# c=a+b"""
from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Soft import of dependencies to avoid crashes when modules are missing
try:  # pragma: no cover
    from modules.safety.guardian import create_approval, require_approval  # type: ignore
except Exception:  # pragma: no cover
    create_approval = require_approval = None  # type: ignore

try:  # pragma: no cover
    from modules.selfmanage.dump_assembler import assemble_from_archive  # type: ignore
except Exception:  # pragma: no cover
    assemble_from_archive = None  # type: ignore

try:  # pragma: no cover
    from modules.selfmanage.usb_locator import list_usb_roots, prepare_ester_folder  # type: ignore
except Exception:  # pragma: no cover
    list_usb_roots = prepare_ester_folder = None  # type: ignore

self_ctrl_bp = Blueprint("self_control", __name__, url_prefix="/self")


@self_ctrl_bp.post("/approvals/create")
@jwt_required()
def approvals_create():
    if create_approval is None:
        return jsonify({"ok": False, "error": "guardian_unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    kind = str(data.get("kind") or "assemble")
    scope = data.get("scope") or {}
    try:
        ttl = int(data.get("ttl") or 3600)
    except Exception:
        ttl = 3600
    try:
        tok = create_approval(kind=kind, scope=scope, ttl_sec=ttl)  # type: ignore[misc]
        return jsonify({"ok": True, "token": tok})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@self_ctrl_bp.post("/assemble_from_dump")
@jwt_required()
def api_assemble_from_dump():
    if require_approval is None or assemble_from_archive is None:
        return jsonify({"ok": False, "error": "assemble_pipeline_unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    path = str(data.get("path") or "").strip()
    target_parent = str(data.get("target_parent") or (os.getenv("ESTER_RUN_ROOT") or os.getcwd()))
    token = data.get("approval_token") or None

    if not path:
        return jsonify({"ok": False, "error": "path is required"}), 400

    try:
        ok, why = require_approval(kind="assemble", scope={"action": "assemble"}, token=token)  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": f"approval check failed: {e}"}), 500

    if not ok:
        return jsonify({"ok": False, "error": f"approval failed: {why}"}), 403

    try:
        res = assemble_from_archive(path, target_parent=target_parent, require_token=False)  # type: ignore[misc]
        code = 200 if (isinstance(res, dict) and res.get("ok")) else 400
        return jsonify(res if isinstance(res, dict) else {"ok": False, "error": "bad assembler response"}), code
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


@self_ctrl_bp.get("/usb/list")
@jwt_required()
def usb_list():
    if list_usb_roots is None:
        return jsonify({"ok": False, "error": "usb_locator_unavailable"}), 500
    only_marked = False
    try:
        only_marked = bool(int(str(request.args.get("marked", "0"))))
    except Exception:
        only_marked = False
    try:
        roots = list_usb_roots(require_sentinel=only_marked)  # type: ignore[misc]
        return jsonify({"ok": True, "roots": roots})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@self_ctrl_bp.post("/usb/prepare")
@jwt_required()
def usb_prepare():
    if prepare_ester_folder is None:
        return jsonify({"ok": False, "error": "usb_locator_unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    mount = str(data.get("mount") or "").strip()
    if not mount or not os.path.isdir(mount):
        return jsonify({"ok": False, "error": "mount is required and must exist"}), 400
    try:
        root = prepare_ester_folder(mount)  # type: ignore[misc]
        return jsonify({"ok": True, "root": root})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


def register_self_control_routes(app) -> None:  # pragma: no cover
    """Historical registration wrapper (compatibility)."""
    app.register_blueprint(self_ctrl_bp)


# Unified project hooks
def register(app) -> None:  # pragma: no cover
    app.register_blueprint(self_ctrl_bp)


def init_app(app) -> None:  # pragma: no cover
    app.register_blueprint(self_ctrl_bp)


__all__ = ["self_ctrl_bp", "register_self_control_routes", "register", "init_app"]
# c=a+b


def register(app):
    app.register_blueprint(self_ctrl_bp)
    return app