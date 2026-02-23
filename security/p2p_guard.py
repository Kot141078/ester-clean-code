# -*- coding: utf-8 -*-
"""
Unified P2P request guard (HMAC + timestamp window).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import socket
import time
from typing import Any, Dict, List, Optional, Tuple

from flask import Request, jsonify, request


def _protected_prefixes() -> List[str]:
    s = os.getenv("P2P_PROTECTED_PREFIXES", "/replication,/p2p")
    return [p.strip() for p in s.split(",") if p.strip()]


def _need_guard(path: str) -> bool:
    return any(str(path or "").startswith(p) for p in _protected_prefixes())


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sign(secret: bytes, ts: str, method: str, path: str, body_sha: str) -> str:
    msg = f"{ts}\n{method.upper()}\n{path}\n{body_sha}".encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def _get_secret() -> bytes:
    return (os.getenv("ESTER_P2P_SECRET", "") or "").encode("utf-8")


def _verify_any(headers: Dict[str, str], method: str, path: str, body: bytes) -> Tuple[bool, Optional[str]]:
    # Legacy compatibility: support X-P2P-Auth as alias for X-P2P-Signature.
    secret = _get_secret()
    if not secret:
        return False, "p2p_signature_required"
    ts = str(headers.get("X-P2P-Ts") or "").strip()
    auth = str(headers.get("X-P2P-Auth") or "").strip()
    if not ts or not auth:
        return False, "p2p_bad_signature"
    body_sha = _sha256(body)
    ref = _sign(secret, ts, method, path, body_sha)
    if hmac.compare_digest(ref, auth):
        return True, None
    return False, "p2p_bad_signature"


def _verify(req: Request) -> Optional[str]:
    """Return None when request is accepted; otherwise error code string."""
    if not _need_guard(req.path):
        return None

    secret = _get_secret()
    if not secret:
        return "p2p_signature_required"

    ts = (req.headers.get("X-P2P-Ts") or "").strip()
    sig = (req.headers.get("X-P2P-Signature") or "").strip()
    if not ts or not sig:
        return "p2p_signature_required"

    try:
        ts_val = int(ts)
    except Exception:
        return "p2p_signature_required"

    win = int(os.getenv("ESTER_P2P_TS_WINDOW", "300") or "300")
    if abs(int(time.time()) - ts_val) > max(1, win):
        return "p2p_clock_skew"

    body = req.get_data(cache=True, as_text=False) or b""
    body_sha = _sha256(body)
    ref = _sign(secret, str(ts_val), req.method, req.path, body_sha)

    err: Optional[str] = None
    if not hmac.compare_digest(ref, sig):
        ok, err = _verify_any(dict(req.headers), req.method, req.path, body)
        if not ok:
            return err or "p2p_bad_signature"

    if err:
        _affect_boost(err)
        try:
            from modules.net.p2p_bloom import add

            add(_sha256(err.encode("utf-8")))
        except Exception:
            # optional tracking, should never break auth path
            pass

    return None


def _affect_boost(error: str) -> float:
    try:
        from modules.affect.priority import score_text

        sc = score_text(error or "")
        return float(sc.get("priority", 1.0))
    except Exception:
        return 1.0


def _gossip_sync_key(new_secret: str) -> None:
    peers = [p.strip() for p in (os.getenv("ESTER_P2P_PEERS", "") or "").split(",") if p.strip()]
    if not peers or not new_secret:
        return
    for peer in peers:
        try:
            host, port = peer.split(":", 1)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect((host, int(port)))
                s.sendall(f"SYNC_P2P_SECRET:{new_secret}".encode("utf-8"))
        except Exception:
            # gossip is optional
            pass


def _log_passport(event: str, data: Dict[str, Any]) -> None:
    try:
        from modules.mem.passport import append as _pp

        _pp(event, data, "security://p2p_guard")
    except Exception:
        pass


def attach_p2p_guard(app) -> None:
    @app.before_request
    def p2p_guard_before_request():
        err = _verify(request)
        if err:
            _log_passport("p2p_guard_error", {"error": err, "path": request.path})
            return jsonify({"ok": False, "error": err}), 401
        return None


def _background_check_keys_from_passport() -> None:
    try:
        from modules.survival.bundle import from_passport

        from_passport(limit=100)
        sec = (os.getenv("ESTER_P2P_SECRET", "") or "").strip()
        if sec:
            _gossip_sync_key(sec)
    except Exception:
        # optional background sync should never break import
        pass


try:
    _background_check_keys_from_passport()
except Exception:
    pass
