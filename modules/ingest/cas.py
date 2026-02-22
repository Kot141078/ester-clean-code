# -*- coding: utf-8 -*-
"""Small CAS helpers used by ingest/vector adapters."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Tuple


def _root() -> Path:
    root = Path(os.getenv("ESTER_CAS_DIR", os.path.join("data", "cas")))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _to_digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _normalize_cid(cid_or_digest: str) -> str:
    raw = str(cid_or_digest or "").strip()
    if raw.startswith("sha256:"):
        return raw.split(":", 1)[1]
    return raw


def get_path(cid_or_digest: str) -> str:
    digest = _normalize_cid(cid_or_digest)
    if not digest:
        return str(_root() / "invalid")
    p = _root() / digest[:2] / digest[2:]
    return str(p)


def put_bytes(blob: bytes) -> Tuple[str, str, int]:
    if not isinstance(blob, (bytes, bytearray)):
        raise TypeError("put_bytes expects bytes-like payload")
    data = bytes(blob)
    digest = _to_digest(data)
    path = Path(get_path(digest))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)
    return f"sha256:{digest}", str(path), len(data)


def read_bytes(cid_or_digest: str) -> bytes:
    p = Path(get_path(cid_or_digest))
    return p.read_bytes()

