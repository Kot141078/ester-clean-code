# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Dict


def _secret() -> bytes:
    raw = (
        os.getenv("GUARDIAN_SECRET")
        or os.getenv("JWT_SECRET")
        or os.getenv("SECRET_KEY")
        or "ester-guardian-local-secret"
    )
    return str(raw).encode("utf-8")


def _b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64u_decode(data: str) -> bytes:
    s = str(data or "")
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_approval(action: str, payload: dict | None = None, ttl_sec: int = 300) -> Dict[str, object]:
    act = str(action or "").strip()
    if not act:
        return {"ok": False, "error": "empty_action"}

    now = float(time.time())
    ttl = max(1.0, float(ttl_sec or 300))
    exp = now + ttl
    nonce = secrets.token_hex(8)
    payload = f"{act}|{now:.6f}|{exp:.6f}|{nonce}"
    sig = _sign(payload)
    token = _b64u_encode(f"{payload}|{sig}".encode("utf-8"))
    return {"ok": True, "token": token, "action": act, "exp": exp}


def validate_approval(token: str, action: str, max_age_sec: int | None = None) -> bool:
    try:
        raw = _b64u_decode(token).decode("utf-8")
        parts = raw.split("|")
        if len(parts) != 5:
            return False
        act, iat_s, exp_s, nonce, sig = parts
        _ = nonce  # structural field, used only to make payload unique
        if act != str(action or "").strip():
            return False
        payload = "|".join(parts[:4])
        if not hmac.compare_digest(_sign(payload), sig):
            return False
        iat = float(iat_s)
        exp = float(exp_s)
        if float(time.time()) >= exp:
            return False
        if max_age_sec is not None and (float(time.time()) - iat) > float(max_age_sec):
            return False
        return True
    except Exception:
        return False


__all__ = ["create_approval", "validate_approval"]
