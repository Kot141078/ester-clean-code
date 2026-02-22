# -*- coding: utf-8 -*-
"""
modules/p2p/bloom.py — stabilnyy Bloom-filtr dlya P2P-deDup: lokalnyy + blob-exchange s merge.

Mosty:
- Yavnyy: (P2P ↔ Dedup) test/dobavlenie ID bez dublikatov v set/pamyat.
- Skrytyy #1: (Profile ↔ Audit) vse operatsii (add/check/merge/reset) logiruem.
- Skrytyy #2: (Mesh/Survival ↔ Rasprostranenie) blob dlya gossip, TTL-reset dlya gigieny.

Zemnoy abzats:
Eto sito dlya dannykh: dublikaty zastrevayut, svezhie proletayut. Ester khikhikaet: "Moi bity — kak pautina: lovyat povtorki, a idei — na volyu!"

# c=a+b
"""
from __future__ import annotations
import os, json, time, math, gzip, base64, hashlib, threading, random
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

FILE = os.getenv("P2P_BLOOM_FILE", "data/p2p/bloom.bin")
META_FILE = os.getenv("P2P_BLOOM_META", "data/p2p/bloom_meta.json")
BITS = int(os.getenv("P2P_BLOOM_BITS", "8388608") or "8388608")  # ~1MB
HASHES = int(os.getenv("P2P_BLOOM_HASHES", "7") or "7")
SALT = os.getenv("P2P_BLOOM_SALT", "ester") or f"ester_{random.randint(0, 9999)}"  # Avto-salt esli pustoy
RESET_DAYS = int(os.getenv("P2P_BLOOM_RESET_DAYS", "7") or "7")

os.makedirs(os.path.dirname(FILE), exist_ok=True)
_lock = threading.RLock()
_state = {"adds": 0, "checks": 0, "imports": 0, "resets": 0}

def _passport(note: str, meta: Dict[str, Any]):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "p2p://bloom")
    except Exception:
        pass

def _bytes_len() -> int:
    return (BITS + 7) // 8

def _empty() -> bytearray:
    return bytearray(_bytes_len())

def _load_meta() -> Dict[str, Any]:
    if not os.path.isfile(META_FILE):
        meta = {"bits": BITS, "k": HASHES, "salt": SALT, "since": int(time.time()), "added": 0}
        json.dump(meta, open(META_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return meta
    meta = json.load(open(META_FILE, "r", encoding="utf-8"))
    # Auto-reset po TTL
    if int(time.time()) - int(meta.get("since", 0)) > RESET_DAYS * 86400:
        reset()
        meta = _load_meta()
    return meta

def _save_meta(meta: Dict[str, Any]):
    json.dump(meta, open(META_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load() -> bytearray:
    meta = _load_meta()  # Obespechivaet reset esli nuzhno
    if not os.path.isfile(FILE):
        buf = _empty()
        with open(FILE, "wb") as f: f.write(buf)
        return buf
    try:
        return bytearray(open(FILE, "rb").read())
    except Exception:
        return _empty()

def _save(buf: bytearray) -> None:
    with open(FILE, "wb") as f: f.write(buf)

def _hashes(s: str) -> List[int]:
    # Double hashing s salt
    h1 = int(hashlib.sha256((SALT + "|" + s).encode("utf-8")).hexdigest(), 16)
    h2 = int(hashlib.sha256((s + "|" + SALT).encode("utf-8")).hexdigest(), 16)
    return [(h1 + i * h2) % BITS for i in range(HASHES)]

def _bit_get(buf: bytearray, pos: int) -> bool:
    bi = pos >> 3; off = pos & 7
    return bool((buf[bi] >> off) & 1)

def _bit_set(buf: bytearray, pos: int):
    bi = pos >> 3; off = pos & 7
    buf[bi] |= (1 << off)

def _fill_ratio(buf: bytearray) -> float:
    ones = sum(bin(b).count("1") for b in buf)
    return float(ones) / float(BITS) if BITS > 0 else 0.0

def status() -> Dict[str, Any]:
    with _lock:
        buf = _load()
        meta = _load_meta()
        p = _fill_ratio(buf)
        n = meta.get("added", 0)
        m = float(meta["bits"]); k = float(meta["k"])
        fpr = (1 - math.exp(-k * n / m)) ** k if m > 0 else 0.0
        return {"ok": True, "meta": dict(meta), "bytes": len(buf), "fill": round(p, 4), "fpr_est": round(fpr, 6), "stats": dict(_state)}

def add(ids: List[str]) -> Dict[str, Any]:
    if not ids: return {"ok": True, "fresh": [], "dup": []}
    with _lock:
        buf = _load()
        meta = _load_meta()
        fresh = []; dup = []
        for s in ids:
            hs = _hashes(str(s))
            seen = all(_bit_get(buf, h) for h in hs)
            if seen:
                dup.append(s)
            else:
                for h in hs: _bit_set(buf, h)
                fresh.append(s)
                meta["added"] += 1
        _save(buf)
        _save_meta(meta)
        _state["adds"] += len(ids)
    _passport("bloom_add", {"fresh": len(fresh), "dup": len(dup)})
    return {"ok": True, "fresh": fresh, "dup": dup}

def check(ids: List[str]) -> Dict[str, Any]:
    if not ids: return {"ok": True, "hits": [], "seen": [], "new": []}
    with _lock:
        buf = _load()
        hits = []; seen = []; new = []
        for s in ids:
            hs = _hashes(str(s))
            hit = all(_bit_get(buf, h) for h in hs)
            hits.append(hit)
            if hit: seen.append(s)
            else: new.append(s)
        _state["checks"] += len(ids)
    _passport("bloom_check", {"seen": len(seen), "new": len(new)})
    return {"ok": True, "hits": hits, "seen": seen, "new": new}

def export_blob() -> Dict[str, Any]:
    with _lock:
        buf = _load()
        meta = _load_meta()
        head = {"bits": meta["bits"], "k": meta["k"], "salt": meta["salt"], "t": int(time.time())}
        gz = gzip.compress(bytes(buf), compresslevel=6)
        b64 = base64.b64encode(gz).decode("ascii")
        return {"ok": True, "blob": {"head": head, "data": b64}}

def import_blob(blob: Dict[str, Any]) -> Dict[str, Any]:
    try:
        head = blob.get("head") or {}
        meta = _load_meta()
        if head.get("bits") != meta["bits"] or head.get("k") != meta["k"] or head.get("salt") != meta["salt"]:
            return {"ok": False, "error": "incompatible_head"}
        data = base64.b64decode(blob.get("data", ""))
        buf_new = bytearray(gzip.decompress(data))
        with _lock:
            buf = _load()
            if len(buf_new) != len(buf):
                return {"ok": False, "error": "size_mismatch"}
            # OR merge
            for i in range(len(buf)):
                buf[i] |= buf_new[i]
            _save(buf)
            _state["imports"] += 1
        _passport("bloom_import", {"merged": True})
        return {"ok": True, "merged": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def reset() -> Dict[str, Any]:
    with _lock:
        _save(_empty())
        meta = _load_meta()
        meta["since"] = int(time.time())
        meta["added"] = 0
        _save_meta(meta)
        _state["resets"] += 1
    _passport("bloom_reset", {})
    return {"ok": True, "reset": True}

def from_passport(limit: int = 5000) -> Dict[str, Any]:
    path = os.getenv("PASSPORT_LOG", "data/passport/log.jsonl")
    if not os.path.isfile(path):
        return {"ok": True, "added": 0, "dup": 0}
    ids = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= limit: break
            line = line.strip()
            if not line: continue
            try:
                rec = json.loads(line)
                if "hash" in rec:
                    ids.append(rec["hash"])
            except Exception:
                continue
    rep = add(ids)
# return {"ok": True, "added": len(rep.get("fresh", [])), "dup": len(rep.get("dup", []))}