# -*- coding: utf-8 -*-
"""
security/rbac_utils.py — legkiy RBAC-dekorator dlya novykh ruchek.

Trebovanie: v JWT (HS256/RS256) est kleym 'roles' (spisok/stroka) i (optsionalno) 'sub'.
Klyuch: berem iz ENV JWT_SECRET_KEY | JWT_SECRET; algoritm: HS256 po umolchaniyu, esli net RS*.

Ne lomaet suschestvuyuschie kontrakty — ispolzuetsya tolko v novykh marshrutakh.

MOSTY:
- Yavnyy: (Bezopasnost ↔ UX) tonkaya proverka roli 'operator' na deystviyakh s RPA.
- Skrytyy #1: (Infoteoriya ↔ Riski) suzhaem dostup — menshe variantov opasnykh vkhodov.
- Skrytyy #2: (Arkhitektura ↔ Psikhologiya) prostoe pravilo «kto mozhet nazhat knopku» snizhaet kognitivnuyu nagruzku.

ZEMNOY ABZATs:
Mini-dekorator bez vneshnikh zavisimostey; pri otsutstvii tokena → 401, pri otsutstvii roli → 403.
Rabotaet oflayn. Dlya lokalnoy otladki mozhno otklyuchit proverku cherez ENV RPA_RBAC_DISABLE=1.

# c=a+b
"""
from __future__ import annotations
import os
from functools import wraps
from typing import Callable, Any, Iterable, Set, Union
from flask import request, jsonify

import base64
import json
import hmac
import hashlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _b64url_decode(s: str) -> bytes:
    s += "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s.encode("ascii"))

def _jwt_decode_hs256(token: str, key: bytes) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("bad_jwt_parts")
    header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
    payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    sig = _b64url_decode(parts[2])
    msg = (parts[0] + "." + parts[1]).encode("ascii")
    calc = hmac.new(key, msg, hashlib.sha256).digest()
    if not hmac.compare_digest(calc, sig):
        raise ValueError("bad_signature")
    alg = header.get("alg", "HS256")
    if alg != "HS256":
        raise ValueError("unsupported_alg")
    return payload

def _extract_roles(claim: Union[str, Iterable[str], None]) -> Set[str]:
    if claim is None:
        return set()
    if isinstance(claim, str):
        return {claim}
    try:
        return {str(x) for x in claim}
    except Exception:
        return set()

def require_role(role: str):
    def deco(fn: Callable[..., Any]):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if os.getenv("RPA_RBAC_DISABLE", "0") == "1":
                return fn(*args, **kwargs)
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return jsonify({"ok": False, "error": "unauthorized"}), 401
            token = auth[7:].strip()
            secret = os.getenv("JWT_SECRET_KEY") or os.getenv("JWT_SECRET") or ""
            if not secret:
                return jsonify({"ok": False, "error": "server_misconfigured"}), 500
            try:
                payload = _jwt_decode_hs256(token, secret.encode("utf-8"))
            except Exception as e:
                return jsonify({"ok": False, "error": f"bad_token:{e}"}), 401
            roles = _extract_roles(payload.get("roles"))
            if role not in roles:
                return jsonify({"ok": False, "error": "forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco