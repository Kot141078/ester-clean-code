# -*- coding: utf-8 -*-
"""security/rbac_middleware.py - RBAC dlya /admin/* i optsionalno /export/*, /board/*.
Rezhimy autentifikatsii: Basic (user/pass or sha256-kheshi) i Token (Bearer/X-Admin-Token). Vstrennyy rate limit.

MOSTY:
- (Yavnyy) RBACMiddleware(app, ...) - edinaya prosloyka bez izmeneniya suschestvuyuschikh routov.
- (Skrytyy #1) Gibkaya matritsa: viewer/operator/admin po prefiksam i metodam (sm. _required_role()).
- (Skrytyy #2) Rate limit per-IP dlya zaschischennoy zony; podderzhka X-Forwarded-For.

ZEMNOY ABZATs:
Privatnye paneli i eksporty zaschischeny: roli, login/parol or token, zaschita ot “zaliva” zaprosami - i vse bez perepisyvaniya koda.

# c=a+b"""
from __future__ import annotations

import base64, os, time
from typing import Optional, Dict, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from .crypto import safe_eq, verify_basic_hash
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_ROLE_RANK = {"viewer": 1, "operator": 2, "admin": 3}

def _get_client_ip(req: Request) -> str:
    hdr = os.getenv("TRUSTED_PROXY_HEADER", "X-Forwarded-For").strip()
    if hdr:
        x = req.headers.get(hdr, "")
        if x:
            return x.split(",")[0].strip()
    return req.client.host if req.client else "0.0.0.0"

def _required_role(path: str, method: str) -> Optional[str]:
    # Explicit rules
    if path == "/admin/control.html":
        return "viewer"
    if path.startswith("/admin/runtime/env"):
        return "viewer" if method.upper() == "GET" else "operator"
    if path.startswith("/admin/webhooks"):
        return "operator"
    if path.startswith("/admin/"):
        return "admin"
    if path.startswith("/export/") and os.getenv("SECURITY_PROTECT_EXPORT", "1") != "0":
        return "operator"
    if path.startswith("/board/") and os.getenv("SECURITY_PROTECT_BOARD", "0") == "1":
        return "viewer"
    return None  # ne zaschischaem

def _rate_limit_key(req: Request) -> Tuple[str, int]:
    ip = _get_client_ip(req)
    now_min = int(time.time() // 60)
    return (ip, now_min)

class _RateBucket:
    __slots__ = ("count", "start_ts")
    def __init__(self) -> None:
        self.count = 0
        self.start_ts = time.time()

class RBACMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, mode: str = "off"):
        super().__init__(app)
        self.mode = (mode or "off").lower()
        self._buckets: Dict[Tuple[str,int], _RateBucket] = {}

    async def dispatch(self, request: Request, call_next):
        need = _required_role(request.url.path, request.method)
        if not need or self.mode == "off":
            return await call_next(request)

        # rate limit
        per_min = int(os.getenv("RATE_LIMIT_ADMIN_PER_MIN", "120") or "120")
        burst = int(os.getenv("RATE_LIMIT_BURST", "60") or "60")
        key = _rate_limit_key(request)
        now = time.time()
        b = self._buckets.get(key)
        if not b or now - b.start_ts > 60:
            b = _RateBucket(); self._buckets[key] = b
        b.count += 1
        if b.count > max(per_min, burst):
            return PlainTextResponse("Too Many Requests", 429)

        # authn → role
        role = None
        if self.mode == "token":
            role = self._auth_token(request)
        elif self.mode == "basic":
            role = self._auth_basic(request)

        if not role:
            return self._unauthorized()

        # authz
        if _ROLE_RANK.get(role, 0) < _ROLE_RANK.get(need, 0):
            return PlainTextResponse("Forbidden", 403)

        return await call_next(request)

    def _unauthorized(self) -> Response:
        realm = os.getenv("SECURITY_REALM", "Ester-Admin")
        r = PlainTextResponse("Unauthorized", 401)
        if self.mode == "basic":
            r.headers["WWW-Authenticate"] = f'Basic realm="{realm}"'
        return r

    def _auth_token(self, req: Request) -> Optional[str]:
        # Header X-Admin-Token (prioritet), zatem Authorization: Bearer
        tok = req.headers.get("X-Admin-Token") or ""
        if not tok:
            auth = req.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                tok = auth[7:].strip()
        if not tok:
            return None
        if safe_eq(tok, os.getenv("ADMIN_TOKEN","")):
            return "admin"
        if safe_eq(tok, os.getenv("OPERATOR_TOKEN","")):
            return "operator"
        if safe_eq(tok, os.getenv("VIEWER_TOKEN","")):
            return "viewer"
        return None

    def _auth_basic(self, req: Request) -> Optional[str]:
        auth = req.headers.get("Authorization","")
        if not auth.lower().startswith("basic "):
            return None
        try:
            userpass = base64.b64decode(auth.split(" ",1)[1]).decode("utf-8")
        except Exception:
            return None
        if ":" not in userpass:
            return None
        user, pwd = userpass.split(":",1)

        # Hashes have priority
        if os.getenv("ADMIN_BASIC_HASH") and verify_basic_hash(user, pwd, os.getenv("ADMIN_BASIC_HASH")):
            return "admin"
        if os.getenv("OPERATOR_BASIC_HASH") and verify_basic_hash(user, pwd, os.getenv("OPERATOR_BASIC_HASH")):
            return "operator"
        if os.getenv("VIEWER_BASIC_HASH") and verify_basic_hash(user, pwd, os.getenv("VIEWER_BASIC_HASH")):
            return "viewer"

        # Inache — pary login/parol
        if os.getenv("ADMIN_BASIC_USER") and safe_eq(user, os.getenv("ADMIN_BASIC_USER")) and safe_eq(pwd, os.getenv("ADMIN_BASIC_PASS","")):
            return "admin"
        if os.getenv("OPERATOR_BASIC_USER") and safe_eq(user, os.getenv("OPERATOR_BASIC_USER")) and safe_eq(pwd, os.getenv("OPERATOR_BASIC_PASS","")):
            return "operator"
        if os.getenv("VIEWER_BASIC_USER") and safe_eq(user, os.getenv("VIEWER_BASIC_USER")) and safe_eq(pwd, os.getenv("VIEWER_BASIC_PASS","")):
            return "viewer"
        return None