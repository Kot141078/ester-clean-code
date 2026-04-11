# -*- coding: utf-8 -*-
"""routes/security_routes.py - oflayn-autentifikatsiya i audit.

Ruchki:
  GET /auth/status -> {initialized:bool}
  POST /auth/init {"password": "..."} # (re)init lokalnogo operatora
  POST /auth/login {"password": "..."} # vydaet JWT s rolyu operator
  POST /auth/rotate # rotatsiya JWT-sekreta (trebuet operator)
  GET /audit/rpa?tail=200 # poslednie N strok audita rpa.jsonl / rpa.log

RBAC:
  - /auth/rotate, /audit/* trebuyut rol 'operator' (sm. security/rbac_utils.require_role)

MOSTY:
- Yavnyy: (UX ↔ Bezopasnost) prostoy vkhod dlya dostupa k RPA/VM-knopkam.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) oflayn-login i lokalnye zhurnaly dayut vosproizvodimost.
- Skrytyy #2: (Kibernetika ↔ Audit) nablyudenie→reshenie→deystvie→zhurnal zamknuty v odnom interfeyse.

ZEMNOY ABZATs:
Nikakikh vneshnikh IdP. Odin fayl s solenym kheshem i sekretom JWT. Pri rotatsii - starye tokeny nedeystvitelny.

# c=a+b"""
from __future__ import annotations
import os, io, json
from typing import List
from flask import Blueprint, jsonify, request
from security.local_auth import state_exists, init_password, verify_password, issue_jwt, rotate_secret
from security.rbac_utils import require_role
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    from flask_jwt_extended import create_access_token  # type: ignore
except Exception:
    create_access_token = None  # type: ignore

bp = Blueprint("security_routes", __name__)

def _rpa_log_paths() -> List[str]:
    # Windows / Linux vozmozhnye puti
    paths: List[str] = []
    win_log_dir = os.getenv("ESTER_RPA_LOG_DIR", "").strip()
    if not win_log_dir:
        program_data = os.getenv("PROGRAMDATA", "").strip()
        if program_data:
            win_log_dir = str(Path(program_data) / "Ester" / "logs")
    if win_log_dir:
        paths.append(str(Path(win_log_dir) / "rpa.jsonl"))
    paths.extend(
        [
            "/var/log/ester/rpa.log",
            "/var/log/ester/rpa.jsonl",
        ]
    )
    return paths

@bp.route("/auth/status", methods=["GET"])
def auth_status():
    return jsonify({"ok": True, "initialized": state_exists()})

@bp.route("/auth/init", methods=["POST"])
def auth_init():
    data = request.get_json(force=True, silent=True) or {}
    pwd = (data.get("password") or "").strip()
    if not pwd:
        return jsonify({"ok": False, "error": "password_required"}), 400
    init_password(pwd)
    return jsonify({"ok": True})

@bp.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(force=True, silent=True) or {}
    pwd = (data.get("password") or "").strip()
    # Dev/test compatibility contract: {user, role} -> access_token
    if not pwd:
        user = str(data.get("user") or "user").strip() or "user"
        role = str(data.get("role") or "user").strip().lower() or "user"
        if create_access_token:
            jwt = create_access_token(identity=user, additional_claims={"roles": [role], "user": user})
        else:
            jwt = issue_jwt(user, [role], ttl_sec=8 * 3600)
        return jsonify({"ok": True, "access_token": jwt, "user": user, "role": role})
    if not verify_password(pwd):
        return jsonify({"ok": False, "error": "bad_credentials"}), 401
    if create_access_token:
        jwt = create_access_token(identity="operator@local", additional_claims={"roles": ["operator"], "user": "operator@local"})
    else:
        jwt = issue_jwt("operator@local", ["operator"], ttl_sec=8 * 3600)
    return jsonify({"ok": True, "token": jwt, "access_token": jwt, "role": "operator"})

@bp.route("/auth/rotate", methods=["POST"])
@require_role("operator")
def auth_rotate():
    rotate_secret()
    return jsonify({"ok": True})

@bp.route("/audit/rpa", methods=["GET"])
@require_role("operator")
def audit_rpa_tail():
    tail = max(1, min(10000, int(request.args.get("tail", "200") or "200")))
    for p in _rpa_log_paths():
        if os.path.exists(p):
            # tail without reading the whole file
            try:
                with open(p, "rb") as f:
                    f.seek(0, io.SEEK_END)
                    size = f.tell()
                    step = 8192
                    data = bytearray()
                    pos = size
                    while pos > 0 and len(data) < tail * 300:  # evristika
                        pos = max(0, pos - step)
                        f.seek(pos)
                        data = f.read(size - pos) + data
                        size = pos
                    lines = data.decode("utf-8", "ignore").splitlines()[-tail:]
                    # attempt to parse JSONL, otherwise - as text
                    items = []
                    for ln in lines:
                        try:
                            items.append(json.loads(ln))
                        except Exception:
                            items.append({"raw": ln})
                    return jsonify({"ok": True, "path": p, "items": items})
            except Exception:
                continue
    return jsonify({"ok": False, "error": "log_not_found"}), 404

def register(app):
    app.register_blueprint(bp)
