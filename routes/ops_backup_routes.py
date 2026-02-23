# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from pathlib import Path
import tempfile
import zipfile
from flask import Blueprint, jsonify, request
try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:
    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn):
            return fn
        return _wrap
try:
    from modules.auth.rbac import has_any_role as _has_any_role
except Exception:
    def _has_any_role(_required):  # type: ignore
        return True

try:
    from config_backup import create_backup, latest_backup_path, verify_backup  # type: ignore
except Exception:
    create_backup = None  # type: ignore
    latest_backup_path = None  # type: ignore
    verify_backup = None  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("ops_backup_routes", __name__)

@bp.get("/ops/backup")
@jwt_required()
def ops_backup_status():
    if not _has_any_role(["ops", "admin"]):
        return jsonify({"ok": False, "error": "rbac deny"}), 403
    root = os.environ.get("ESTER_DATA_ROOT") or os.path.join(os.getcwd(), "data")
    backup_dir = Path(root) / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return jsonify({"ok": True, "backup_dir": str(backup_dir)})


def _is_safe_path(base_dir: str, candidate: str) -> bool:
    base_abs = os.path.abspath(base_dir)
    cand_abs = os.path.abspath(candidate)
    return cand_abs == base_abs or cand_abs.startswith(base_abs + os.sep)


def _restore_zip(path: str, target_dir: str) -> None:
    target_abs = os.path.abspath(target_dir)
    os.makedirs(target_abs, exist_ok=True)

    with zipfile.ZipFile(path, "r") as zf:
        for info in zf.infolist():
            name = str(info.filename or "").replace("\\", "/")
            if not name or name.endswith("/"):
                continue
            if name.startswith("meta/"):
                continue
            if name.startswith("payload/"):
                name = name[len("payload/") :]
            if not name:
                continue

            out_path = os.path.abspath(os.path.join(target_abs, name))
            if not _is_safe_path(target_abs, out_path):
                raise ValueError(f"unsafe archive path: {info.filename}")

            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with zf.open(info, "r") as src, open(out_path, "wb") as dst:
                dst.write(src.read())


@bp.post("/ops/backup/run")
@jwt_required()
def ops_backup_run():
    if not _has_any_role(["ops", "operator", "admin"]):
        return jsonify({"ok": False, "error": "rbac deny"}), 403
    if not callable(create_backup):
        return jsonify({"ok": False, "error": "backup_module_unavailable"}), 503
    try:
        zip_path, sig_path = create_backup()
        return jsonify({"ok": True, "zip": zip_path, "path": zip_path, "sig": sig_path})
    except Exception as exc:
        # On locked/readonly project dirs, retry in temp backup dir.
        msg = str(exc)
        if "WinError 5" in msg or "Permission" in msg:
            try:
                fallback = os.path.join(tempfile.gettempdir(), "ester-backups")
                os.makedirs(fallback, exist_ok=True)
                zip_path, sig_path = create_backup(output_dir=fallback)
                return jsonify({"ok": True, "zip": zip_path, "path": zip_path, "sig": sig_path})
            except Exception as retry_exc:
                return jsonify({"ok": False, "error": str(retry_exc)}), 503
        return jsonify({"ok": False, "error": msg}), 503


@bp.post("/ops/backup/verify")
@jwt_required()
def ops_backup_verify():
    if not _has_any_role(["ops", "operator", "admin"]):
        return jsonify({"ok": False, "error": "rbac deny"}), 403
    if not callable(verify_backup):
        return jsonify({"ok": False, "error": "backup_module_unavailable"}), 503

    payload = request.get_json(silent=True) or {}
    path = str(payload.get("path") or "").strip()
    if not path and callable(latest_backup_path):
        path = str(latest_backup_path() or "").strip()
    if not path or not os.path.isfile(path):
        return jsonify({"ok": False, "error": "not found"}), 400

    valid = bool(verify_backup(path))
    return jsonify({"ok": True, "valid": valid, "path": path}), 200


@bp.post("/ops/backup/restore")
@jwt_required()
def ops_backup_restore():
    if not _has_any_role(["ops", "operator", "admin"]):
        return jsonify({"ok": False, "error": "rbac deny"}), 403
    if not callable(verify_backup):
        return jsonify({"ok": False, "error": "backup_module_unavailable"}), 503

    payload = request.get_json(silent=True) or {}
    path = str(payload.get("path") or "").strip()
    if not path and callable(latest_backup_path):
        path = str(latest_backup_path() or "").strip()
    if not path or not os.path.isfile(path):
        return jsonify({"ok": False, "error": "not found"}), 400

    target = str(payload.get("target") or payload.get("target_dir") or "").strip()
    if not target:
        target = os.path.join(os.path.dirname(path), "restore_tmp")

    if not bool(verify_backup(path)):
        return jsonify({"ok": False, "error": "invalid backup"}), 400

    try:
        _restore_zip(path, target)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "path": path, "target": target, "target_dir": target}), 200
