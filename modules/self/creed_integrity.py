# -*- coding: utf-8 -*-
"""Creed integrity helpers.

Provides fingerprinting, anchor file management, append-only event chain,
optional Ed25519 signature verification, and consistency checks against memory."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional

_CNT = {"anchor_inits": 0, "verify_calls": 0, "verify_ok": 0, "verify_fail": 0, "chain_appends": 0}

ROOT = "data/self"
ANCHOR_PATH = os.path.join(ROOT, "creed_anchor.json")
CHAIN_PATH = os.path.join(ROOT, "creed_chain.jsonl")
PUBKEY_PATH = os.path.join(ROOT, "creed_pubkey.txt")  # base64 Ed25519 public key
SIG_PATH = os.path.join(ROOT, "creed_signature.bin")  # signature bytes for sha256 digest

AB = (os.getenv("CREED_INTEGRITY_AB", "A") or "A").upper()
STRICT = bool(int(os.getenv("CREED_IMMUTABLE_ENFORCE", "0")))
CHAIN_MAX = int(os.getenv("CREED_CHAIN_MAX", "2000"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256(text.encode("utf-8"))


def _b32(data: bytes) -> str:
    return base64.b32encode(data).decode("ascii").rstrip("=")


def _short(hexstr: str, n: int = 12) -> str:
    return hexstr[:n].upper()


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _save_json(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def _append_chain(event: Dict[str, Any]) -> Dict[str, Any]:
    """Append one event with linked hashes (prev_hash -> own_hash)."""
    os.makedirs(os.path.dirname(CHAIN_PATH), exist_ok=True)
    prev = ""
    try:
        with open(CHAIN_PATH, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            if size > 0:
                chunk = min(4096, size)
                fh.seek(-chunk, os.SEEK_END)
                tail = fh.read().decode("utf-8", "ignore")
                lines = [ln for ln in tail.splitlines() if ln.strip()]
                for line in reversed(lines):
                    try:
                        last = json.loads(line)
                        prev = str(last.get("own_hash") or "")
                        if prev:
                            break
                    except Exception:
                        continue
    except Exception:
        prev = ""

    record = {"ts": int(time.time()), **event, "prev_hash": prev}
    own_hash = _sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    record["own_hash"] = own_hash
    with open(CHAIN_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    _CNT["chain_appends"] += 1
    return record


def _verify_signature(sha_hex: str) -> Optional[bool]:
    """
    Verify Ed25519 signature for creed digest if key and signature files exist.
    Returns:
      - True/False when verification is possible
      - None when signature data is unavailable
    """
    if not (os.path.isfile(PUBKEY_PATH) and os.path.isfile(SIG_PATH)):
        return None
    try:
        import nacl.exceptions  # type: ignore
        import nacl.signing  # type: ignore

        pk_b64 = open(PUBKEY_PATH, "r", encoding="utf-8").read().strip()
        sig = open(SIG_PATH, "rb").read()
        verify_key = nacl.signing.VerifyKey(base64.b64decode(pk_b64))
        digest = bytes.fromhex(sha_hex)
        try:
            verify_key.verify(digest, sig)
            return True
        except nacl.exceptions.BadSignatureError:
            return False
    except Exception:
        return None


def fingerprint() -> Dict[str, Any]:
    """Return creed fingerprint and provenance snapshot."""
    from modules.self.core_creed import CORE_CREED_TEXT, creed_passport  # type: ignore

    sha_hex = _sha256_text(CORE_CREED_TEXT)
    return {
        "ok": True,
        "sha256": sha_hex,
        "base32": _b32(bytes.fromhex(sha_hex)),
        "short": _short(sha_hex),
        "passport": creed_passport(),
        "sig_verification": _verify_signature(sha_hex),
    }


def anchor_init(force: bool = False) -> Dict[str, Any]:
    """Create/update anchor file using current creed fingerprint."""
    if AB == "B":
        return {"ok": False, "error": "CREED_INTEGRITY_AB=B"}

    fp = fingerprint()
    if not fp.get("ok"):
        return {"ok": False, "error": "fingerprint_failed"}

    if os.path.isfile(ANCHOR_PATH) and not force:
        existing = _load_json(ANCHOR_PATH) or {}
        if existing.get("sha256") == fp["sha256"]:
            return {"ok": True, "created": False, "anchor": existing}

    anchor = {
        "sha256": fp["sha256"],
        "created_ts": int(time.time()),
        "passport": fp["passport"],
        "sig_verification": fp.get("sig_verification"),
        "note": "Immutable anchor for core creed",
    }
    _save_json(ANCHOR_PATH, anchor)
    _append_chain({"event": "anchor_init", "sha256": fp["sha256"]})
    _CNT["anchor_inits"] += 1
    return {"ok": True, "created": True, "anchor": anchor}


def _memory_sha_candidates() -> List[str]:
    """Best-effort extraction of creed hashes from memory records."""
    out: List[str] = []
    try:
        from services.mm_access import get_mm  # type: ignore

        mm = get_mm()
        search = getattr(mm, "search", None) or getattr(mm, "find", None)
        if not search:
            return []
        for query in ("creed", "ester:core", "owner:profile"):
            try:
                rows = (search(q=query, k=10) or {}).get("items", [])
                for row in rows:
                    prov = dict(((row or {}).get("meta") or {}).get("provenance") or {})
                    sha = str(prov.get("text_sha256") or "").strip()
                    if sha:
                        out.append(sha)
            except Exception:
                continue
    except Exception:
        return []
    # Unique values, preserve order
    return list(dict.fromkeys(out))


def verify() -> Dict[str, Any]:
    """Verify consistency: code creed <-> anchor file <-> memory evidence."""
    _CNT["verify_calls"] += 1

    fp = fingerprint()
    sha = str(fp.get("sha256") or "")
    anchor = _load_json(ANCHOR_PATH) or {}
    anchor_ok = bool(anchor.get("sha256") == sha)

    mem_candidates = _memory_sha_candidates()
    mem_ok = (not mem_candidates) or (sha in mem_candidates)

    sig_ok = fp.get("sig_verification")
    ok = bool(anchor_ok and mem_ok and (sig_ok is True or sig_ok is None))
    _append_chain({"event": "verify", "anchor_ok": anchor_ok, "mem_ok": mem_ok, "sig_ok": sig_ok})
    _CNT["verify_ok" if ok else "verify_fail"] += 1

    report = {
        "ok": ok,
        "sha256": sha,
        "anchor_ok": anchor_ok,
        "mem_candidates": mem_candidates,
        "sig_ok": sig_ok,
    }
    if STRICT and not ok:
        report["enforced"] = True
    return report


def chain_tail(limit: int = CHAIN_MAX) -> Dict[str, Any]:
    """Return recent chain entries."""
    rows: List[Dict[str, Any]] = []
    try:
        with open(CHAIN_PATH, "r", encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        if limit > 0 and len(lines) > limit:
            lines = lines[-limit:]
        for line in lines:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        rows = []
    return {"ok": True, "tail": rows}


def counters() -> Dict[str, int]:
    return dict(_CNT)
