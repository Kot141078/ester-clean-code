# -*- coding: utf-8 -*-
"""modules/auth/auto_jwt.py - avtonomnyy HS256-JWT (bez vneshnikh paketov).

MOSTY:
- (Yavnyy) mint_jwt()/verify_jwt() + ensure_papa_cookie() dlya drop-in portala.
- (Skrytyy #1) Chitaet sekrety iz ENV (ESTER_JWT_SECRET/JWT_SECRET_KEY/JWT_SECRET), fail-closed po umolchaniyu.
- (Skrytyy #2) Vstraivaetsya v lyuboy Flask-router bez izmeneniya suschestvuyuschey avtorizatsii.

ZEMNOY ABZATs:
Nadezhnyy “klyuch zazhiganiya”: formiruem i proveryaem token sami - bez storonnikh bibliotek i bez plyasok s bubnom.

# c=a+b"""
from __future__ import annotations
import os, json, hmac, hashlib, time, base64
from typing import Any, Dict, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_DEV_EPHEMERAL_SECRET: Optional[bytes] = None
_DEV_SECRET_WARNED = False


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _b64url_decode(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + pad)

def _now() -> int:
    return int(time.time())

def _env_secret() -> str:
    for name in ("ESTER_JWT_SECRET", "JWT_SECRET_KEY", "JWT_SECRET"):
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""

def _secret() -> bytes:
    global _DEV_EPHEMERAL_SECRET, _DEV_SECRET_WARNED

    configured = _env_secret()
    if configured:
        return configured.encode("utf-8")

    if (os.getenv("ESTER_DEV_MODE", "0").strip() == "1"):
        if _DEV_EPHEMERAL_SECRET is None:
            _DEV_EPHEMERAL_SECRET = os.urandom(32)
        if not _DEV_SECRET_WARNED:
            _DEV_SECRET_WARNED = True
            print("[auto_jwt] WARNING: DEV MODE ephemeral JWT secret in use; tokens invalid after restart.")
        return _DEV_EPHEMERAL_SECRET

    raise RuntimeError(
        "JWT secret is required. Set ESTER_JWT_SECRET (or JWT_SECRET_KEY/JWT_SECRET). "
        "For local dev only, set ESTER_DEV_MODE=1 to use an ephemeral secret."
    )

def mint_jwt(sub: str, roles: Optional[list] = None, aud: str = "ester", iss: str = "ester.local", ttl_days: int = None) -> str:
    secret = _secret()
    ttl = int(os.getenv("JWT_TTL_DAYS", "30")) if ttl_days is None else int(ttl_days)
    header = {"alg": "HS256", "typ": "JWT"}
    now = _now()
    payload = {
        "sub": sub,
        "aud": aud,
        "iss": iss,
        "iat": now,
        "exp": now + ttl * 86400,
        "roles": roles or ["admin"]
    }
    h = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("ascii")
    sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    s = _b64url(sig)
    return f"{h}.{p}.{s}"

def verify_jwt(token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    secret = _secret()
    try:
        h, p, s = token.split(".")
        signing_input = f"{h}.{p}".encode("ascii")
        expected = hmac.new(secret, signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(s)):
            return False, None
        payload = json.loads(_b64url_decode(p).decode("utf-8"))
        if payload.get("exp", 0) < _now():
            return False, None
        return True, payload
    except Exception:
        return False, None

def ensure_papa_cookie(resp, username: str = None) -> None:
    """If there are no cookies, it puts down the ZhVT for Dad."""
    try:
        from flask import request
        if request.cookies.get("jwt") or request.cookies.get("Authorization"):
            return
    except Exception:
        pass
    user = username or os.getenv("ESTER_DEFAULT_USER") or os.getenv("ADMIN_USERNAMES", "Owner").split(",")[0]
    tok = mint_jwt(user, roles=["admin","owner"])
    try:
        resp.set_cookie("jwt", tok, httponly=True, samesite="Lax", max_age=30*86400, path="/")
        resp.set_cookie("Authorization", f"Bearer {tok}", httponly=False, samesite="Lax", max_age=30*86400, path="/")
    except Exception:
        pass
# c=a+b
