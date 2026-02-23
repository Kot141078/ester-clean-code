# -*- coding: utf-8 -*-
"""
security.e2ee — prostaya E2EE-obertka.
MOSTY:
- (Yavnyy) routes.* ↔ e2ee.encrypt/decrypt
- (Skrytyy 1) ENV ↔ klyuch: ESTER_E2EE_KEY (base64/utf-8/proizvolnaya stroka)
- (Skrytyy 2) Zavisimosti ↔ offlayn: snachala probuem cryptography.Fernet, inache XOR-folbek.
ZEMNOY ABZATs:
Edinoe API dlya rezervnykh kopiy i P2P: rabotaet i s cryptography, i bez nee (offlayn).
c=a+b
"""
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
    # Snachala probuem kak base64, inache delaem sha256 ot stroki
    try:
        kb = base64.urlsafe_b64decode(raw.encode("utf-8"))
        if kb:
            return kb
    except Exception:
        pass
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
    # XOR fallback — offlayn bez vneshnikh paketov
    k = _key_bytes()
    return bytes([b ^ k[i % len(k)] for i, b in enumerate(data)])

def decrypt(data: bytes) -> bytes:
    ok, f = _get_fernet()
    if ok and f:
        return f.decrypt(data)  # type: ignore[attr-defined]
    k = _key_bytes()
    return bytes([b ^ k[i % len(k)] for i, b in enumerate(data)])