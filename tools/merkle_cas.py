# -*- coding: utf-8 -*-
"""
tools/merkle_cas.py — merkle-derevo poverkh CAS (sha256).
Koren schitaetsya ot otsortirovannykh listev vida "sha256:<hex>".
"""
from __future__ import annotations

import hashlib
import os
from typing import Iterable, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

CAS_DIR = os.getenv("ESTER_CAS_DIR", os.path.join("data", "cas"))

def _hash_pair(a: str, b: str) -> str:
    h = hashlib.sha256()
    h.update(a.encode("utf-8"))
    h.update(b.encode("utf-8"))
    return h.hexdigest()

def merkle_root(digests: Iterable[str]) -> str:
    leaves = sorted([d.split(":", 1)[1] if ":" in d else d for d in digests])
    if not leaves:
        return "0" * 64
    layer: List[str] = leaves[:]
    while len(layer) > 1:
        nxt: List[str] = []
        for i in range(0, len(layer), 2):
            if i + 1 < len(layer):
                nxt.append(_hash_pair(layer[i], layer[i + 1]))
            else:
                # dubliruem posledniy (standartnyy priem)
                nxt.append(_hash_pair(layer[i], layer[i]))
        layer = nxt
    return layer[0]
