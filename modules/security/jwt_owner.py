# -*- coding: utf-8 -*-
"""
modules.security.jwt_owner — owner JWT generator (oflayn, bez vneshnikh lib).
API: generate_owner_jwt(email:str|None=None) -> str
# c=a+b
"""
from __future__ import annotations
import os, time, hmac, hashlib, base64, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
def _secret() -> bytes:
    raw = os.getenv("JWT_SECRET") or os.getenv("ESTER_OWNER_SECRET") or "ester-owner-secret"
    return raw.encode("utf-8")
def generate_owner_jwt(email: str | None = None) -> str:
    payload = {"sub": email or (os.getenv("ESTER_OWNER_EMAIL") or "owner@local"), "iat": int(time.time())}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(',',':')).encode("utf-8")).rstrip(b"=")
    sig  = base64.urlsafe_b64encode(hmac.new(_secret(), body, hashlib.sha256).digest()).rstrip(b"=")
    return f"owner.{body.decode('utf-8')}.{sig.decode('utf-8')}"