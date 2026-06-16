# -*- coding: utf-8 -*-
"""growth_engine.witness - tamper-evident ledger for every behavior change.

Same discipline as l4w_witness / ArlWitnessLedger in ester-clean-code:
- append-only JSONL,
- each record hash-chained via prev_hash,
- canonical hashing,
- optional Ed25519 signature if `cryptography` is available, else hash-only
  (graceful degrade, like the original).

Every promotion, rejection, rollback and demotion of a behavior version MUST
pass through here. Opacity becomes liability; a change with no witnessed footprint
is not allowed to count.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from .common import canonical_bytes, hash_obj, now_ts, ok, err

try:  # pragma: no cover - environment dependent
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    _ED25519_OK = True
except Exception:  # pragma: no cover
    serialization = None  # type: ignore
    Ed25519PrivateKey = None  # type: ignore
    Ed25519PublicKey = None  # type: ignore
    _ED25519_OK = False


WITNESS_SCHEMA = "growth.witness.v1"
_VALID_EVENTS = {
    "candidate_proposed",
    "shadow_eval",
    "promotion",
    "rejected",
    "rollback",
    "demotion",
}


def _record_hash_input(record: Dict[str, Any]) -> Dict[str, Any]:
    src = dict(record or {})
    src.pop("sig", None)
    src = dict(src)
    src.pop("footprint_hash", None)
    return src


class GrowthWitnessLedger:
    """Append-only, hash-chained ledger persisted as JSONL."""

    def __init__(self, root: str | os.PathLike, *, priv_key_path: str = "") -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = (self.root / "growth_witness.jsonl").resolve()
        self._priv_key_path = str(priv_key_path or "").strip()

    # --- chain io -----------------------------------------------------------
    def _load(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    row = __import__("json").loads(s)
                except Exception:
                    continue
                if isinstance(row, dict):
                    out.append(row)
        return out

    def head_hash(self) -> str:
        rows = self._load()
        if not rows:
            return ""
        return str(rows[-1].get("footprint_hash") or "")

    # --- signing (optional) -------------------------------------------------
    def _maybe_sign(self, payload_hash: str) -> Dict[str, Any]:
        if not _ED25519_OK or not self._priv_key_path:
            return {"alg": "none", "signed": False}
        try:
            blob = Path(self._priv_key_path).read_bytes()
            sk = serialization.load_pem_private_key(blob, password=None)
            if not isinstance(sk, Ed25519PrivateKey):
                return {"alg": "none", "signed": False}
            sig = sk.sign(bytes.fromhex(payload_hash))
            import base64

            return {"alg": "ed25519", "signed": True, "sig_b64": base64.b64encode(sig).decode("ascii")}
        except Exception:
            return {"alg": "none", "signed": False}

    # --- append -------------------------------------------------------------
    def append(self, event_type: str, subject: Dict[str, Any]) -> Dict[str, Any]:
        et = str(event_type or "").strip()
        if et not in _VALID_EVENTS:
            return err("WITNESS_EVENT_INVALID", f"unknown_event:{et}")
        prev = self.head_hash()
        record: Dict[str, Any] = {
            "schema": WITNESS_SCHEMA,
            "ts": now_ts(),
            "event_type": et,
            "subject": dict(subject or {}),
            "prev_hash": prev,
        }
        fp = hash_obj(_record_hash_input(record))
        record["footprint_hash"] = fp
        record["sig"] = self._maybe_sign(fp)
        line = __import__("json").dumps(record, ensure_ascii=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        return ok(footprint_hash=fp, prev_hash=prev, record=record)

    # --- verify -------------------------------------------------------------
    def verify_chain(self) -> Dict[str, Any]:
        rows = self._load()
        expected_prev = ""
        for idx, row in enumerate(rows):
            recomputed = hash_obj(_record_hash_input(row))
            if str(row.get("footprint_hash") or "") != recomputed:
                return err("GROWTH_WITNESS_HASH_MISMATCH", "footprint_mismatch", index=idx)
            if str(row.get("prev_hash") or "") != expected_prev:
                return err("GROWTH_WITNESS_CHAIN_BROKEN", "prev_mismatch", index=idx)
            expected_prev = recomputed
        return ok(footprints=len(rows), last_hash=expected_prev)

    def records(self) -> List[Dict[str, Any]]:
        return self._load()
