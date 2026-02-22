# -*- coding: utf-8 -*-
"""
modules/p2p/bloom_filter.py — myagkiy P2P-filtr (Bloom) dlya obyavleniy «chto uzhe videli».

API:
  • add_many(ids:list[str]) -> dict
  • check_many(ids:list[str]) -> dict  # {"present":[...], "absent":[...]}
  • export_bits() -> bytes

Konfig:
  • P2P_BLOOM_BITS (razmer bitovoy matritsy), P2P_BLOOM_HASHES (chislo khesh-funktsiy)

Mosty:
- Yavnyy: (Set ↔ Memory) sokraschaem dubli pri obmene dokumentami mezhdu uzlami.
- Skrytyy #1: (Infoteoriya ↔ Effektivnost) kompaktnye obyavleniya bez peresylki massivov id.
- Skrytyy #2: (Kibernetika ↔ Kontrol) stateless API — legko sinkhronizirovat s peers.

Zemnoy abzats:
Eto «sito»: esli dokument uzhe proseyan — vtoroy raz ne gonyaem po seti.

# c=a+b
"""
from __future__ import annotations

import hashlib
import os
from typing import Dict, Iterable, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_BITS = int(os.getenv("P2P_BLOOM_BITS", "1048576"))
_HS = int(os.getenv("P2P_BLOOM_HASHES", "3"))
_BUF = bytearray(_BITS // 8)

def _idxes(item: str) -> List[int]:
    raw = hashlib.sha256(item.encode("utf-8")).digest()
    out = []
    for i in range(_HS):
        h = int.from_bytes(raw[i*8:(i+1)*8], "big")
        out.append(h % _BITS)
    return out

def add_many(ids: Iterable[str]) -> Dict[str, int]:
    n = 0
    for s in (ids or []):
        for i in _idxes(str(s)):
            _BUF[i // 8] |= (1 << (i % 8))
        n += 1
    return {"ok": 1, "added": n}

def check_many(ids: Iterable[str]) -> Dict[str, List[str]]:
    present, absent = [], []
    for s in (ids or []):
        ok = True
        for i in _idxes(str(s)):
            if not (_BUF[i // 8] & (1 << (i % 8))):
                ok = False; break
        (present if ok else absent).append(str(s))
    return {"ok": 1, "present": present, "absent": absent}

def export_bits() -> bytes:
    return bytes(_BUF)
