# -*- coding: utf-8 -*-
"""HMAC helpers for replication and P2P verification."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Mapping, MutableMapping, Optional, Tuple

_REPLAY_CACHE: MutableMapping[str, float] = {}
_REPLAY_LOCK = Lock()


def _to_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    return str(value).encode("utf-8", errors="ignore")


def get_hmac_key() -> bytes:
    val = (
        os.getenv("P2P_HMAC_KEY")
        or os.getenv("REPLICATION_HMAC_KEY")
        or os.getenv("HMAC_KEY")
        or os.getenv("ESTER_HMAC_KEY")
        or "ester-hmac-key"
    )
    return _to_bytes(val)


def sign(data: Any, key: Any = None, out: str = "hex") -> str:
    """Return HMAC-SHA256 in `hex` or `b64`."""
    payload = _to_bytes(data)
    secret = _to_bytes(key) if key is not None else get_hmac_key()
    digest = hmac.new(secret, payload, hashlib.sha256).digest()
    fmt = str(out or "hex").lower()
    if fmt == "b64":
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return digest.hex()


def verify(data: Any, key: Any, signature: str) -> bool:
    """Compatibility verify(data, key, signature)."""
    sig = str(signature or "").strip().lower()
    expect_hex = sign(data, key, out="hex").lower()
    if sig.startswith("hmac-"):
        sig = sig[len("hmac-") :]
    if sig.startswith("hmac-sha256:"):
        sig = sig.split(":", 1)[1]
    if sig.startswith("sha256="):
        raw = sign(data, key, out="b64")
        return hmac.compare_digest(sig, f"sha256={raw}")
    return hmac.compare_digest(sig, expect_hex)


def hmac_verify(blob: bytes, sig: str, key: Any = None) -> bool:
    return verify(blob, get_hmac_key() if key is None else key, sig)


def header_signature(data: bytes, key: Any = None) -> str:
    """Header format used by replication routes: `hmac-<hex>`."""
    return "hmac-" + sign(data, key if key is not None else get_hmac_key(), out="hex")


def _parse_keys_map() -> Dict[str, str]:
    raw = (os.getenv("P2P_HMAC_KEYS") or "").strip()
    out: Dict[str, str] = {}
    for token in raw.split(","):
        token = token.strip()
        if not token or ":" not in token:
            continue
        kid, key = token.split(":", 1)
        out[kid.strip()] = key.strip()
    fallback = get_hmac_key().decode("utf-8", errors="ignore")
    if not out:
        out["default"] = fallback
    elif fallback and fallback not in out.values():
        out["default"] = fallback
    return out


def _problem(title: str, detail: str = "", status: Optional[int] = None) -> Dict[str, Any]:
    p: Dict[str, Any] = {"title": title}
    if detail:
        p["detail"] = detail
    if status is not None:
        p["status"] = int(status)
    return p


def _canonical(method: str, path: str, ts: str, body: bytes) -> str:
    return f"{str(method).upper()}|{path}|{ts}|{hashlib.sha256(body).hexdigest()}"


def _parse_ts(ts_raw: str) -> Optional[int]:
    s = str(ts_raw or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except Exception:
        pass
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


def _check_replay(req_id: str) -> bool:
    now = float(time.time())
    ttl = max(1, int(os.getenv("P2P_REPLAY_TTL_SEC", "60") or "60"))
    with _REPLAY_LOCK:
        expired = [k for k, until in _REPLAY_CACHE.items() if until < now]
        for k in expired:
            _REPLAY_CACHE.pop(k, None)
        if req_id in _REPLAY_CACHE:
            return False
        _REPLAY_CACHE[req_id] = now + ttl
        return True


def _legacy_verify_headers(body: bytes, headers: Mapping[str, Any]) -> bool:
    norm = {str(k).lower(): str(v) for k, v in dict(headers).items()}
    got = norm.get("x-signature") or norm.get("signature") or ""
    if not got:
        return False
    return hmac_verify(body, got)


def verify_headers(*args):
    """
    Compatibility variants:
      verify_headers(body_bytes, headers) -> bool
      verify_headers(method, path, body_bytes, headers) -> (bool, problem|None)
    """
    if len(args) == 2:
        body, headers = args
        return _legacy_verify_headers(_to_bytes(body), headers or {})

    if len(args) != 4:
        return False, _problem("bad_arguments", "expected 4 args", status=400)

    method, path, body, headers = args
    body_b = _to_bytes(body)
    hdr: Dict[str, str] = {str(k).lower(): str(v) for k, v in dict(headers or {}).items()}
    required = os.getenv("P2P_SIGNING_REQUIRED", "1") == "1"
    if not required:
        return True, None

    sig = hdr.get("x-p2p-signature", "").strip().lower()
    if not sig:
        return False, _problem("bad_signature", "missing_signature", status=401)

    ts_raw = hdr.get("x-p2p-timestamp", "")
    ts_val = _parse_ts(ts_raw)
    if ts_val is None:
        return False, _problem("drift", "missing_or_bad_timestamp", status=400)

    drift = max(1, int(os.getenv("P2P_DRIFT_SEC", "120") or "120"))
    now = int(time.time())
    if abs(now - ts_val) > drift:
        return False, _problem("drift", "timestamp_out_of_window", status=400)

    keys_map = _parse_keys_map()
    kid = (hdr.get("x-p2p-key-id") or "").strip()
    can = _canonical(str(method), str(path), str(ts_raw), body_b).encode("utf-8")

    def _verify_with(secret: str) -> bool:
        expected = hmac.new(secret.encode("utf-8"), can, hashlib.sha256).hexdigest().lower()
        return hmac.compare_digest(expected, sig)

    ok_sig = False
    if kid and kid in keys_map:
        ok_sig = _verify_with(keys_map[kid])
    else:
        for secret in keys_map.values():
            if _verify_with(secret):
                ok_sig = True
                break
    if not ok_sig:
        return False, _problem("bad_signature", status=401)

    req_id = (hdr.get("x-request-id") or "").strip()
    if req_id and not _check_replay(req_id):
        return False, _problem("replay", status=409)

    return True, None
