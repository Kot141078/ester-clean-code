# -*- coding: utf-8 -*-
"""
Admin P2P API endpoints used by templates/admin_p2p.html.

Fail-closed contract:
- ready read-only operations may return 200;
- not-ready write/apply path returns 501 JSON (never fake success).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

bp = Blueprint("admin_p2p", __name__)

AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()
_DATA_ROOT = Path(os.getenv("ESTER_P2P_DATA_DIR", "data/p2p"))
_QUEUE_NAMES = ("inbox", "outbox", "pending", "sent", "failed")
_WRITE_ROLES = {"admin", "operator"}


def _rbac_write_ok() -> bool:
    if (os.getenv("RBAC_REQUIRED", "true").strip().lower() == "false"):
        return True
    try:
        from modules.auth.rbac import has_any_role  # type: ignore

        return bool(has_any_role(sorted(_WRITE_ROLES)))
    except Exception:
        header = (request.headers.get("X-User-Roles") or request.headers.get("X-Roles") or "").strip()
        roles = {x.strip().lower() for x in header.split(",") if x.strip()}
        return bool(roles & _WRITE_ROLES)


def _safe_queue_entries(name: str, limit: int = 50) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    folder = _DATA_ROOT / name
    try:
        if not folder.is_dir():
            return out
        files = sorted(
            [p for p in folder.iterdir() if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for p in files[: max(1, min(limit, 500))]:
            try:
                st = p.stat()
                out.append(
                    {
                        "name": p.name,
                        "size": int(st.st_size),
                        "mtime": int(st.st_mtime),
                    }
                )
            except Exception:
                out.append({"name": p.name, "size": 0, "mtime": 0})
    except Exception:
        return []
    return out


@bp.post("/admin/p2p/api/scan")
def api_scan():
    if not _rbac_write_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403

    queues: Dict[str, Dict[str, Any]] = {}
    for name in _QUEUE_NAMES:
        rows = _safe_queue_entries(name, limit=10)
        queues[name] = {"count": len(rows), "items": rows}
    return jsonify({"ok": True, "ab_mode": AB_MODE, "data_root": str(_DATA_ROOT), "queues": queues})


@bp.post("/admin/p2p/api/pack")
def api_pack():
    if not _rbac_write_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    try:
        limit = int(data.get("limit", 50))
    except Exception:
        return jsonify({"ok": False, "error": "bad_limit"}), 400

    rows = _safe_queue_entries("outbox", limit=max(1, min(limit, 500)))
    payload = {"kind": "p2p_pack_preview", "count": len(rows), "items": rows}
    return jsonify({"ok": True, "ab_mode": AB_MODE, "dry": AB_MODE != "B", "payload": payload})


@bp.post("/admin/p2p/api/apply")
def api_apply():
    if not _rbac_write_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403

    return (
        jsonify(
            {
                "ok": False,
                "error": "not_implemented",
                "hint": "wire admin_p2p.api_apply to internal inbox apply pipeline",
            }
        ),
        501,
    )


def register(app):
    app.register_blueprint(bp)
    return app

