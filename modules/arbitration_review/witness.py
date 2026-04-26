"""ARL witness footprint ledger.

This is Stage 3 as a sidecar: ARL events get a durable, hash-chained
footprint without wiring the live runtime witness subsystem.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .layer import ArlEvent, ArlEventType, to_record

SCHEMA = "ester.arl.witness_footprint.v1"
_HEX64 = set("0123456789abcdef")


@dataclass(frozen=True)
class ArlWitnessFootprint:
    schema: str
    footprint_id: str
    witness_id: str
    witness_kind: str
    dispute_id: str
    event_id: str
    event_type: ArlEventType
    occurred_at: str
    recorded_at: str
    event_hash: str
    payload_hash: str
    prev_hash: str = ""
    footprint_hash: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class ArlWitnessLedger:
    """Explicit-root JSONL ledger for ARL witness footprints."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.base_dir = self.root / "arl"
        self.witness_path = self.base_dir / "witness.jsonl"

    def append_event(
        self,
        event: ArlEvent,
        *,
        witness_id: str,
        witness_kind: str = "arl_sidecar",
        details: dict[str, Any] | None = None,
    ) -> ArlWitnessFootprint:
        prev_hash = self.last_hash()
        footprint = build_witness_footprint(
            event,
            witness_id=witness_id,
            witness_kind=witness_kind,
            prev_hash=prev_hash,
            details=details,
        )
        self.append_footprint(footprint)
        return footprint

    def append_events(
        self,
        events: Iterable[ArlEvent],
        *,
        witness_id: str,
        witness_kind: str = "arl_sidecar",
    ) -> tuple[ArlWitnessFootprint, ...]:
        footprints = []
        for event in events:
            footprints.append(
                self.append_event(event, witness_id=witness_id, witness_kind=witness_kind)
            )
        return tuple(footprints)

    def append_footprint(self, footprint: ArlWitnessFootprint) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.witness_path.parent.mkdir(parents=True, exist_ok=True)
        with self.witness_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(to_record(footprint), ensure_ascii=False, sort_keys=True) + "\n")
        return self.witness_path

    def load_footprints(self) -> list[dict[str, Any]]:
        if not self.witness_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.witness_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
        return rows

    def last_hash(self) -> str:
        rows = self.load_footprints()
        if not rows:
            return ""
        return str(rows[-1].get("footprint_hash") or "").strip().lower()

    def verify_chain(self) -> dict[str, Any]:
        rows = self.load_footprints()
        prev_hash = ""
        for index, row in enumerate(rows):
            rep = verify_witness_footprint(row)
            if not bool(rep.get("ok")):
                return {**rep, "index": index}
            row_prev = str(row.get("prev_hash") or "").strip().lower()
            if row_prev != prev_hash:
                return {
                    "ok": False,
                    "error_code": "ARL_WITNESS_PREV_HASH_MISMATCH",
                    "index": index,
                    "expected_prev_hash": prev_hash,
                    "actual_prev_hash": row_prev,
                }
            prev_hash = str(row.get("footprint_hash") or "").strip().lower()
        return {
            "ok": True,
            "schema": SCHEMA,
            "footprints": len(rows),
            "last_hash": prev_hash,
        }


def build_witness_footprint(
    event: ArlEvent,
    *,
    witness_id: str,
    witness_kind: str = "arl_sidecar",
    prev_hash: str = "",
    recorded_at: str | None = None,
    details: dict[str, Any] | None = None,
) -> ArlWitnessFootprint:
    wid = str(witness_id or "").strip()
    if not wid:
        raise ValueError("witness_id_required")
    prev = str(prev_hash or "").strip().lower()
    if prev and not _is_sha256_hex(prev):
        raise ValueError("prev_hash_invalid")
    footprint = ArlWitnessFootprint(
        schema=SCHEMA,
        footprint_id=f"arl_witness:{uuid4().hex}",
        witness_id=wid,
        witness_kind=str(witness_kind or "arl_sidecar").strip() or "arl_sidecar",
        dispute_id=event.dispute_id,
        event_id=event.event_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        recorded_at=recorded_at or _now_iso(),
        event_hash=event_hash(event),
        payload_hash=payload_hash(event),
        prev_hash=prev,
        details=dict(details or {}),
    )
    return _with_footprint_hash(footprint)


def verify_witness_footprint(row: ArlWitnessFootprint | dict[str, Any]) -> dict[str, Any]:
    payload = to_record(row)
    if not isinstance(payload, dict):
        return {"ok": False, "error_code": "ARL_WITNESS_INVALID", "error": "invalid_payload"}
    if payload.get("schema") != SCHEMA:
        return {"ok": False, "error_code": "ARL_WITNESS_SCHEMA_INVALID", "schema": payload.get("schema")}
    claimed = str(payload.get("footprint_hash") or "").strip().lower()
    if not _is_sha256_hex(claimed):
        return {"ok": False, "error_code": "ARL_WITNESS_HASH_INVALID", "footprint_hash": claimed}
    prev = str(payload.get("prev_hash") or "").strip().lower()
    if prev and not _is_sha256_hex(prev):
        return {"ok": False, "error_code": "ARL_WITNESS_PREV_HASH_INVALID", "prev_hash": prev}
    computed = footprint_hash(payload)
    if computed != claimed:
        return {
            "ok": False,
            "error_code": "ARL_WITNESS_FOOTPRINT_HASH_MISMATCH",
            "claimed_hash": claimed,
            "computed_hash": computed,
        }
    return {
        "ok": True,
        "schema": SCHEMA,
        "footprint_hash": claimed,
        "prev_hash": prev,
    }


def event_hash(event: ArlEvent) -> str:
    return _sha256_hex(_canonical_bytes(event))


def payload_hash(event: ArlEvent) -> str:
    return _sha256_hex(_canonical_bytes(event.payload))


def footprint_hash(row: ArlWitnessFootprint | dict[str, Any]) -> str:
    payload = to_record(row)
    if not isinstance(payload, dict):
        payload = {}
    payload = dict(payload)
    payload["footprint_hash"] = ""
    return _sha256_hex(_canonical_bytes(payload))


def _with_footprint_hash(footprint: ArlWitnessFootprint) -> ArlWitnessFootprint:
    payload = to_record(footprint)
    object.__setattr__(footprint, "footprint_hash", footprint_hash(payload))
    return footprint


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _to_primitive(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _to_primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _to_primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_primitive(item) for item in value]
    return value


def _sha256_hex(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(char in _HEX64 for char in value)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
