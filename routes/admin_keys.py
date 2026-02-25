# -*- coding: utf-8 -*-
"""Admin: Klyuchi i podpisi (oflayn).

Most (yavnyy):
- (Kibernetika ↔ UX) Yavnoe sozdanie/prosmotr klyuchey i test podpisi - prozrachnyy kontrol doveriya.

Mosty (skrytye):
- (Infoteoriya ↔ Ekonomika) Fingerprint - deshevaya identifikatsiya, udobnaya dlya katalogov par.
- (Logika ↔ Nadezhnost) Klyuchi lezhat lokalno, private ne ukhodit v set/logi.

Zemnoy abzats:
Panel sozdaet Ed25519 (ili HMAC fallback) klyuchi v ESTER/keys, pokazyvaet publichnyy klyuch i fingerprint,
daet test: podpisat mini-peyload i proverit verifikatsiyu."""
from __future__ import annotations

import os
import time
from typing import Any, Dict
from flask import Blueprint, jsonify, render_template, request

# We do not change contracts: we leave import paths as in the dump
try:
    from modules.crypto.keys import ensure_keys, load_meta, load_public_pem  # type: ignore
except Exception:
    def ensure_keys(*args, **kwargs):  # type: ignore
        raise RuntimeError("crypto keys backend unavailable")

    def load_meta(*args, **kwargs):  # type: ignore
        return None

    def load_public_pem(*args, **kwargs):  # type: ignore
        return b""

try:
    from modules.crypto.signing import sign_payload, verify_payload  # type: ignore
except Exception:
    def sign_payload(*args, **kwargs):  # type: ignore
        raise RuntimeError("crypto signing backend unavailable")

    def verify_payload(*args, **kwargs):  # type: ignore
        return False, "signing backend unavailable"
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_keys", __name__, url_prefix="/admin/keys")

# A/B slot for secure self-editing
AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()


@bp.get("/")
def page():
    meta_dict: Dict[str, Any] | None = None
    pub = ""
    error = ""
    try:
        meta = load_meta()
        meta_dict = vars(meta) if meta else None
    except Exception as e:
        error = f"load_meta failed: {e}"
    try:
        pub = (load_public_pem() or b"").decode("utf-8", errors="ignore")
    except Exception as e:
        error = (error + "; " if error else "") + f"load_public_pem failed: {e}"

    if error:
        meta_dict = dict(meta_dict or {})
        meta_dict["ui_error"] = error
    return render_template("admin_keys.html", ab_mode=AB_MODE, meta=meta_dict, pub=pub)


@bp.post("/init")
def api_init():
    try:
        meta = ensure_keys(now_ts=int(time.time()))
        return jsonify({"ok": True, "ab": AB_MODE, "meta": vars(meta)})
    except Exception as e:
        return jsonify({"ok": False, "ab": AB_MODE, "error": f"init failed: {e}"}), 200


@bp.post("/sign_test")
def api_sign_test():
    data = request.get_json(silent=True) or {}
    payload = data.get("payload") or {"ping": "pong", "ts": int(time.time())}
    try:
        sig = sign_payload(payload)
        ok, note = verify_payload(payload, sig)
        return jsonify({"ok": ok, "note": note, "sig": sig, "payload": payload})
    except Exception as e:
        return jsonify({"ok": False, "note": f"sign_test failed: {e}", "payload": payload}), 200


def register(app):  # pragma: no cover
    """Blueprint registration (drop-in)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


__all__ = ["bp", "register", "init_app"]
