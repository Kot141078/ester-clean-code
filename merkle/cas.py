# -*- coding: utf-8 -*-
"""
merkle.cas — minimalnyy kontent-adresnyy stor (CAS)
# c=a+b
"""
from __future__ import annotations
import json
import os
import hashlib
from pathlib import Path
from typing import Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _root() -> Path:
    base = os.getenv("PERSIST_DIR") or os.path.join(os.getcwd(), "data")
    p = Path(base) / "cas"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

class CAS:
    def __init__(self, base_dir: Optional[str] = None):
        self._base = Path(base_dir) if base_dir else _root()
        self._base.mkdir(parents=True, exist_ok=True)

    def _blob(self, data: Any) -> bytes:
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
        if isinstance(data, str):
            return data.encode("utf-8")
        # Deterministic JSON for object payloads.
        return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )

    def put(self, data: Any) -> str:
        blob = self._blob(data)
        h = _digest(blob)
        path = self._base / h[:2] / h[2:]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(blob)
        return h

    def get(self, digest: str) -> Optional[bytes]:
        path = self._base / digest[:2] / digest[2:]
        return path.read_bytes() if path.exists() else None
