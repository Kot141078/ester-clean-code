# -*- coding: utf-8 -*-
"""
Admin peers API endpoints used by templates/admin_peers.html.
"""
from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Dict

from flask import Blueprint, jsonify, request

bp = Blueprint("admin_peers", __name__)

AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()
_WRITE_ROLES = {"admin", "operator"}
_TRUST_VALUES = {"trusted", "unknown", "blocked"}
_REGISTRY_PATH = Path(os.getenv("ESTER_PEERS_REGISTRY_PATH", "data/p2p/peers_registry.json"))


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


def _load_registry() -> Dict[str, Any]:
    try:
        if not _REGISTRY_PATH.is_file():
            return {"peers": {}}
        data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"peers": {}}
        peers = data.get("peers")
        if not isinstance(peers, dict):
            data["peers"] = {}
        return data
    except Exception:
        return {"peers": {}}


def _save_registry(data: Dict[str, Any]) -> None:
    _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REGISTRY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_handshake(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return {}
        try:
            raw = json.loads(raw)
        except Exception:
            return {}
    if not isinstance(raw, dict):
        return {}
    return raw


@bp.post("/admin/peers/api/scan")
def api_scan():
    if not _rbac_write_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    reg = _load_registry()
    return jsonify({"ok": True, "ab_mode": AB_MODE, "peers": reg.get("peers", {})})


@bp.post("/admin/peers/api/trust")
def api_trust():
    if not _rbac_write_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    fpr = str(data.get("fpr") or "").strip()
    trust = str(data.get("trust") or "").strip().lower()
    if not fpr:
        return jsonify({"ok": False, "error": "fpr_required"}), 400
    if trust not in _TRUST_VALUES:
        return jsonify({"ok": False, "error": "bad_trust"}), 400

    reg = _load_registry()
    peers = reg.setdefault("peers", {})
    rec = dict(peers.get(fpr) or {})
    rec["trust"] = trust
    rec["last_seen"] = int(time.time())
    rec["seen_count"] = int(rec.get("seen_count") or 0)
    peers[fpr] = rec

    if AB_MODE == "B":
        _save_registry(reg)
        return jsonify({"ok": True, "ab_mode": AB_MODE, "fpr": fpr, "trust": trust, "saved": True})
    return jsonify({"ok": True, "ab_mode": AB_MODE, "fpr": fpr, "trust": trust, "dry": True, "saved": False})


@bp.get("/admin/peers/api/export")
def api_export():
    if not _rbac_write_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403

    node = (os.getenv("ESTER_NODE_ID") or socket.gethostname() or "ester-node").strip()
    pubkey = (os.getenv("ESTER_P2P_PUBKEY") or "").strip()
    fingerprint = (os.getenv("ESTER_P2P_FINGERPRINT") or "").strip()
    payload = {
        "node": node,
        "pubkey": pubkey,
        "fingerprint": fingerprint,
        "ts": int(time.time()),
    }
    return jsonify({"ok": True, "ab_mode": AB_MODE, "handshake": payload})


@bp.post("/admin/peers/api/import")
def api_import():
    if not _rbac_write_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    hs = _normalize_handshake(data.get("handshake"))
    if not hs:
        return jsonify({"ok": False, "error": "bad_handshake"}), 400

    fpr = str(hs.get("fingerprint") or "").strip()
    if not fpr:
        return jsonify({"ok": False, "error": "fingerprint_required"}), 400

    reg = _load_registry()
    peers = reg.setdefault("peers", {})
    rec = dict(peers.get(fpr) or {})
    rec["name"] = str(hs.get("node") or rec.get("name") or "").strip()
    rec["pubkey"] = str(hs.get("pubkey") or rec.get("pubkey") or "").strip()
    rec["trust"] = str(rec.get("trust") or "unknown")
    rec["last_seen"] = int(time.time())
    rec["seen_count"] = int(rec.get("seen_count") or 0) + 1
    peers[fpr] = rec

    if AB_MODE == "B":
        _save_registry(reg)
        return jsonify({"ok": True, "ab_mode": AB_MODE, "imported": fpr, "saved": True})
    return jsonify({"ok": True, "ab_mode": AB_MODE, "imported": fpr, "dry": True, "saved": False})


def register(app):
    app.register_blueprint(bp)
    return app

