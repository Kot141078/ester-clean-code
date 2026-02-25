# -*- coding: utf-8 -*-
"""security.e2ee - prostaya obertka E2EE. Use cryptography.Fernet, esli dostupna; inache - XOR.

MOSTY:
- (Yavnyy) routes.* ↔ e2ee.encrypt/decrypt
- (Skrytyy #1) ENV ↔ klyuch: ESTER_E2EE_KEY (base64/utf-8)
- (Skrytyy #2) Bezopasnost ↔ Praktika: myagkaya degradatsiya bez cryptography.

ZEMNOY ABZATs:
Dlya rezervnykh kopiy i P2P: one API, kotoroe “gorit” dazhe bez vneshnikh paketov v offlayne.
# c=a+b"""
from __future__ import annotations
import base64, hashlib, os
from typing import Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from cryptography.fernet import Fernet  # type: ignore
except Exception:  # pragma: no cover
    Fernet = None  # type: ignore

def _key_bytes() -> bytes:
    raw = os.getenv("ESTER_E2EE_KEY") or "ester-offline-key"
    try:
        return base64.urlsafe_b64decode(raw.encode("utf-8"))
    except Exception:
        return hashlib.sha256(raw.encode("utf-8")).digest()

def _get_fernet() -> Tuple[bool, object | None]:
    if Fernet is None:
        return False, None
    key = _key_bytes()
    if len(key) != 32:
        key = hashlib.sha256(key).digest()
    fkey = base64.urlsafe_b64encode(key)
    return True, Fernet(fkey)

def encrypt(data: bytes) -> bytes:
    ok, f = _get_fernet()
    if ok and f:
        return f.encrypt(data)  # type: ignore[attr-defined]
    # XOR fallback
    k = _key_bytes()
    return bytes([b ^ k[i % len(k)] for i, b in enumerate(data)])

def decrypt(data: bytes) -> bytes:
    ok, f = _get_fernet()
    if ok and f:
        return f.decrypt(data)  # type: ignore[attr-defined]
    k = _key_bytes()
    return bytes([b ^ k[i % len(k)] for i, b in enumerate(data)])