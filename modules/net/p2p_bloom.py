# -*- coding: utf-8 -*-
"""modules/net/p2p_bloom.py - lokalnyy i vneshniy Bloom-filtry dlya deduplikatsii obmena id mezhdu uzlami.

What does it mean:
  • Khranit osnovnoy Bloom (bloom.bin) s parametrami m (bity) i k (kheshi), schetchik add().
  • Eksport/import binarnika; MERGE s odinakovymi parametrami - pobitovoe OR.
    Pri nesovpadenii parametrov - sokhranyaem kak vneshniy filtr (external/*.bin) i uchityvaem pri check().
  • Registration pachek id (register_ids) i proverka chlenstva (check_ids).
  • State/metadannye v state.json.

ENV:
  • P2P_BLOOM_ENABLED=1 | 0
  • P2P_BLOOM_M=2097152 (2M bit) — ~0.24 MB
  • P2P_BLOOM_K=6

Mosty:
- Yavnyy: (Memory ↔ Set) deshevyy test “videl/ne videl” dlya id replik/profileov bez trafika.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) obedinenie filtrov (OR) bez sovmestnoy indeksatsii.
- Skrytyy #2: (Kibernetika ↔ Masshtab) vneshnie filtry ne lomayut skhemu — prosto uchityvayutsya pri check().

Zemnoy abzats:
Eto ramka na vyezde so sklada: na letu skaniruet shtrikhkod korobki i mashet rukoy - “eto uzhe bylo” or “vpervye vizhu”.

# c=a+b"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any, Dict, Iterable, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ENABLED = bool(int(os.getenv("P2P_BLOOM_ENABLED", "1")))
M = int(os.getenv("P2P_BLOOM_M", "2097152"))  # bits
K = int(os.getenv("P2P_BLOOM_K", "6"))

_DIR = os.path.join("data", "p2p")
_MAIN = os.path.join(_DIR, "bloom.bin")
_STATE = os.path.join(_DIR, "state.json")
_EXT_DIR = os.path.join(_DIR, "external")

os.makedirs(_DIR, exist_ok=True)
os.makedirs(_EXT_DIR, exist_ok=True)

_bits: bytearray | None = None
_count: int = 0

def _load():
    global _bits, _count
    if _bits is not None:
        return
    nbytes = (M + 7) // 8
    if os.path.isfile(_MAIN):
        data = bytearray(open(_MAIN, "rb").read())
        if len(data) < nbytes:
            data.extend(b"\x00" * (nbytes - len(data)))
        _bits = data[:nbytes]
    else:
        _bits = bytearray(b"\x00" * nbytes)
    if os.path.isfile(_STATE):
        try:
            st = json.load(open(_STATE, "r", encoding="utf-8"))
            _count = int(st.get("count", 0))
        except Exception:
            _count = 0

def _save():
    if _bits is None:
        return
    with open(_MAIN, "wb") as f:
        f.write(_bits)
    with open(_STATE, "w", encoding="utf-8") as f:
        json.dump({"m": M, "k": K, "count": _count}, f, ensure_ascii=False, indent=2)

def _hashes(s: str) -> List[int]:
    # we use SHA-256 with different prefixes (for independent functions)
    out: List[int] = []
    raw = s.encode("utf-8")
    for i in range(K):
        h = hashlib.sha256(bytes([i]) + raw).digest()
        # vozmem 8 bayt → uint64 → mod M
        idx = int.from_bytes(h[:8], "big") % M
        out.append(idx)
    return out

def add(s: str) -> None:
    if not ENABLED or not s:
        return
    _load()
    global _count
    for idx in _hashes(s):
        byte_i = idx // 8
        bit_i = idx % 8
        _bits[byte_i] |= (1 << bit_i)
    _count += 1
    _save()

def register_ids(ids: Iterable[str]) -> int:
    n = 0
    for s in ids or []:
        if isinstance(s, str) and s:
            add(s)
            n += 1
    return n

def contains(s: str) -> bool:
    if not ENABLED or not s:
        return False
    _load()
    for idx in _hashes(s):
        byte_i = idx // 8
        bit_i = idx % 8
        if not (_bits[byte_i] & (1 << bit_i)):
            # check external filters
            break
    else:
        return True
    # vneshniy nabor
    for name in os.listdir(_EXT_DIR):
        if not name.endswith(".bin"):
            continue
        path = os.path.join(_EXT_DIR, name)
        try:
            data = memoryview(open(path, "rb").read())
            meta = json.loads(open(path + ".json", "r", encoding="utf-8").read())
            m2 = int(meta.get("m", M)); k2 = int(meta.get("k", K))
            # if the parameters are different, we will recalculate the indices for k2/m2 and check
            raw = s.encode("utf-8")
            ok = True
            for i in range(k2):
                h = hashlib.sha256(bytes([i]) + raw).digest()
                idx = int.from_bytes(h[:8], "big") % m2
                byte_i = idx // 8
                bit_i = idx % 8
                if not (data[byte_i] & (1 << bit_i)):
                    ok = False; break
            if ok:
                return True
        except Exception:
            continue
    return False

def check_ids(ids: Iterable[str]) -> List[bool]:
    return [contains(s) for s in (ids or [])]

def export_main() -> bytes:
    _load()
    return bytes(_bits)

def merge_blob(blob: bytes, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """If meta.m/meta.k match - OP to the main filter.
    Otherwise, we put it as external (external/<sna>.bin + .zhsion)."""
    _load()
    m2 = int((meta or {}).get("m", M))
    k2 = int((meta or {}).get("k", K))
    if m2 == M and k2 == K:
        nbytes = (M + 7) // 8
        buf = memoryview(blob)[:nbytes]
        for i in range(nbytes):
            _bits[i] |= buf[i]
        _save()
        return {"ok": True, "mode": "or", "m": M, "k": K}
    # save as external
    sha = hashlib.sha256(blob).hexdigest()[:16]
    path = os.path.join(_EXT_DIR, f"{sha}.bin")
    with open(path, "wb") as f:
        f.write(blob)
    with open(path + ".json", "w", encoding="utf-8") as f:
        json.dump({"m": m2, "k": k2}, f, ensure_ascii=False)
    return {"ok": True, "mode": "external", "file": path}

def state() -> Dict[str, Any]:
    _load()
    exts: List[Dict[str, Any]] = []
    for name in os.listdir(_EXT_DIR):
        if name.endswith(".bin"):
            meta_path = os.path.join(_EXT_DIR, name + ".json")
            meta = {}
            try:
                meta = json.load(open(meta_path, "r", encoding="utf-8"))
            except Exception:
                pass
            exts.append({"file": os.path.join(_EXT_DIR, name), **meta})
    return {"ok": True, "enabled": ENABLED, "m": M, "k": K, "count": _count, "externals": exts}

def merge_base64(b64: str, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    try:
        blob = base64.b64decode(b64)
    except Exception as e:
        return {"ok": False, "error": f"base64 decode: {e}"}
    return merge_blob(blob, meta=meta or {})
