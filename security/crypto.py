# -*- coding: utf-8 -*-
"""
security/crypto.py — utility dlya bezopasnykh sravneniy i proverki kheshey.

MOSTY:
- (Yavnyy) verify_basic_hash(user, passwd, hex_hash) — sverka sha256("user:pass") s hex.
- (Skrytyy #1) Ispolzuetsya RBAC middleware dlya Basic podsistemy.
- (Skrytyy #2) safe_eq — konstantno-vremennoe sravnenie strok/bayt.

ZEMNOY ABZATs:
Khranit parol «kak est» — plokho. Dazhe bez vneshnikh zavisimostey mozhno sveryat po kheshu i ne svetit sekret v konfige.

# c=a+b
"""
from __future__ import annotations

import hashlib, hmac
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def safe_eq(a: str | bytes, b: str | bytes) -> bool:
    if isinstance(a, str): a = a.encode("utf-8")
    if isinstance(b, str): b = b.encode("utf-8")
    return hmac.compare_digest(a, b)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def verify_basic_hash(user: str, passwd: str, hex_hash: Optional[str]) -> bool:
    if not hex_hash:
        return False
    return safe_eq(sha256_hex(f"{user}:{passwd}"), hex_hash.strip().lower())