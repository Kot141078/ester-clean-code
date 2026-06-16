# -*- coding: utf-8 -*-
"""growth_engine.common - shared primitives.

Mirrors the idioms found in ester-clean-code:
- fail-closed env gates (parse_bool_env / require_env_exact),
- canonical, deterministic JSON for hashing (sorted keys, floats forbidden),
- ok-shaped result dicts.

Honest scope note (read this once, applies to the whole package):
this package implements *bounded instrumental self-improvement* - a measurable,
reversible loop that makes tools / policies / routing / memory weights provably
better against an external fitness signal. It is NOT "becoming", consciousness,
subjecthood, or open-ended self-rewriting. Authority is rented from reality, not
accumulated from rhetoric.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, Iterable

_BOOL_TRUE = {"1", "true", "yes", "on", "y"}


def now_ts() -> int:
    return int(time.time())


def parse_bool_env(name: str, default: bool) -> bool:
    raw_default = "1" if bool(default) else "0"
    raw = str(os.getenv(name, raw_default) or raw_default).strip().lower()
    return raw in _BOOL_TRUE


def require_env_exact(name: str, expected: str) -> bool:
    return str(os.getenv(name, "") or "").strip() == str(expected)


def env_int(name: str, default: int, min_value: int = 0) -> int:
    try:
        value = int(os.getenv(name, str(default)) or default)
    except Exception:
        value = int(default)
    return max(int(min_value), int(value))


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except Exception:
        return float(default)


def q(x: float, ndigits: int = 6) -> str:
    """Quantize a float to a fixed-precision string so it can enter a hash
    deterministically (floats are forbidden inside canonical_bytes)."""
    return f"{float(x):.{int(ndigits)}f}"


def _ensure_canonical(value: Any, where: str = "$") -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        raise ValueError(f"float_forbidden:{where} (quantize with q())")
    if isinstance(value, list):
        for i, item in enumerate(value):
            _ensure_canonical(item, f"{where}[{i}]")
        return
    if isinstance(value, dict):
        for k, item in value.items():
            if not isinstance(k, str):
                raise ValueError(f"dict_key_not_str:{where}")
            _ensure_canonical(item, f"{where}.{k}")
        return
    raise ValueError(f"type_forbidden:{where}:{type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    _ensure_canonical(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_hex(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def hash_obj(value: Any) -> str:
    return sha256_hex(canonical_bytes(value))


def ok(**kw: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": True}
    out.update(kw)
    return out


def err(error_code: str, error: str = "", **kw: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "error_code": str(error_code), "error": str(error or error_code)}
    out.update(kw)
    return out


def mean(xs: Iterable[float]) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0
