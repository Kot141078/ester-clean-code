# -*- coding: utf-8 -*-
"""
modules/auth/auto_jwt.py — avtonomnyy HS256-JWT (bez vneshnikh paketov).

MOSTY:
- (Yavnyy) mint_jwt()/verify_jwt() + ensure_papa_cookie() dlya drop-in portala.
- (Skrytyy #1) Chitaet sekrety iz .env (JWT_SECRET/JWT_SECRET_KEY), fallback na konstantu.
- (Skrytyy #2) Vstraivaetsya v lyuboy Flask-router bez izmeneniya suschestvuyuschey avtorizatsii.

ZEMNOY ABZATs:
Nadezhnyy «klyuch zazhiganiya»: formiruem i proveryaem token sami — bez storonnikh bibliotek i bez plyasok s bubnom.

# c=a+b
"""
from __future__ import annotations
import os, json, hmac, hashlib, time, base64
from typing import Any, Dict, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _b64url_decode(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + pad)

def _now() -> int:
    return int(time.time())

def _secret() -> bytes:
    s = os.getenv("JWT_SECRET_KEY") or os.getenv("JWT_SECRET") or "ester-dev-secret"
    return s.encode("utf-8")

def mint_jwt(sub: str, roles: Optional[list] = None, aud: str = "ester", iss: str = "ester.local", ttl_days: int = None) -> str:
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
    sig = hmac.new(_secret(), signing_input, hashlib.sha256).digest()
    s = _b64url(sig)
    return f"{h}.{p}.{s}"

def verify_jwt(token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    try:
        h, p, s = token.split(".")
        signing_input = f"{h}.{p}".encode("ascii")
        expected = hmac.new(_secret(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(s)):
            return False, None
        payload = json.loads(_b64url_decode(p).decode("utf-8"))
        if payload.get("exp", 0) < _now():
            return False, None
        return True, payload
    except Exception:
        return False, None

def ensure_papa_cookie(resp, username: str = None) -> None:
    """
    Esli kuki net — prostavlyaet JWT dlya Papa.
    """
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