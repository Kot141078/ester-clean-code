"""Minimal operator pointers for SYNAPS Codex handoffs.

The pointer is the only text meant for human chat/Telegram relay. Full
contracts, patches, reports, and logs should stay in SYNAPS quarantine.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .protocol import SynapsValidationError


CODEX_HANDOFF_POINTER_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_HANDOFF_POINTER_WRITE"
CODEX_HANDOFF_POINTER_SCHEMA = "ester.synaps.codex_handoff_pointer.v1"
DEFAULT_CODEX_HANDOFF_POINTER_ROOT = Path("data") / "synaps" / "codex_bridge" / "handoff_pointers"
_SECRET_TERMS = (
    "OPENAI_API_KEY=",
    "SISTER_SYNC_TOKEN=",
    "Authorization: Bearer ",
    "authorization: bearer ",
    "BEGIN PRIVATE KEY",
    "payload_b64",
)


@dataclass(frozen=True)
class CodexHandoffPointerPolicy:
    max_title_chars: int = 120
    max_note_chars: int = 240
    max_transfer_ids: int = 30

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def build_codex_handoff_pointer(
    *,
    gate: str,
    title: str,
    accepted_transfer_ids: Sequence[str],
    source_files: Sequence[str | Path] = (),
    patch_sha256: str = "",
    rejected_transfer_ids: Sequence[str] = (),
    note: str = "",
    forbid_terms: Sequence[str] = (),
    policy: CodexHandoffPointerPolicy | None = None,
) -> dict[str, Any]:
    actual_policy = policy or CodexHandoffPointerPolicy()
    safe_gate = _safe_text(gate, 32)
    safe_title = _safe_text(title, actual_policy.max_title_chars)
    accepted = [_safe_identifier(item) for item in accepted_transfer_ids]
    rejected = [_safe_identifier(item) for item in rejected_transfer_ids]
    if not safe_gate:
        raise SynapsValidationError("gate is required")
    if not accepted:
        raise SynapsValidationError("at least one accepted transfer id is required")
    if len(accepted) > actual_policy.max_transfer_ids:
        raise SynapsValidationError("too many accepted transfer ids")

    sources = [_source_record(path) for path in source_files]
    record = {
        "schema": CODEX_HANDOFF_POINTER_SCHEMA,
        "created_at": _iso_now(),
        "gate": safe_gate,
        "title": safe_title,
        "accepted_transfer_ids": accepted,
        "rejected_transfer_ids": rejected,
        "patch_sha256": _safe_sha256(patch_sha256),
        "source_files": sources,
        "note": _safe_text(note, actual_policy.max_note_chars),
        "auto_ingest": False,
        "memory": "off",
    }
    text = _render_pointer(record)
    problems = validate_operator_pointer_text(text, forbid_terms=forbid_terms)
    return {
        "ok": not problems,
        "schema": CODEX_HANDOFF_POINTER_SCHEMA,
        "gate": safe_gate,
        "record": record,
        "text": text,
        "problems": problems,
        "policy": actual_policy.to_record(),
        "auto_ingest": False,
        "memory": "off",
    }


def write_codex_handoff_pointer(
    payload: Mapping[str, Any],
    *,
    output_path: str | Path,
    confirm: str,
) -> dict[str, Any]:
    if confirm != CODEX_HANDOFF_POINTER_CONFIRM_PHRASE:
        return {"ok": False, "status": "gate_failed", "problems": ["missing_codex_handoff_pointer_confirm_phrase"]}
    if not payload.get("ok"):
        return {"ok": False, "status": "validation_failed", "problems": list(payload.get("problems") or [])}
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(payload["text"]), encoding="utf-8", newline="\n")
    return {
        "ok": True,
        "status": "written",
        "path": str(target),
        "sha256": _sha256_bytes(str(payload["text"]).encode("utf-8")),
        "auto_ingest": False,
        "memory": "off",
    }


def validate_operator_pointer_text(text: str, *, forbid_terms: Sequence[str] = ()) -> list[str]:
    problems: list[str] = []
    for term in [*_SECRET_TERMS, *forbid_terms]:
        if term and term in text:
            problems.append(f"forbidden_term_present:{term}")
    if "```" in text:
        problems.append("pointer_must_not_include_code_fences")
    return problems


def _render_pointer(record: Mapping[str, Any]) -> str:
    lines = [
        "# SYNAPS Codex Handoff Pointer",
        "",
        f"Gate: `{record['gate']}`",
        f"Title: {record['title']}",
        "",
        "Accepted transfers:",
    ]
    lines.extend(f"- `{item}`" for item in record["accepted_transfer_ids"])
    if record.get("rejected_transfer_ids"):
        lines.extend(["", "Rejected or unconfirmed transfers, do not use:"])
        lines.extend(f"- `{item}`" for item in record["rejected_transfer_ids"])
    if record.get("patch_sha256"):
        lines.extend(["", f"Patch SHA256: `{record['patch_sha256']}`"])
    if record.get("source_files"):
        lines.extend(["", "Local source file hashes, no file content included:"])
        for item in record["source_files"]:
            lines.append(f"- `{item['name']}` size `{item['size']}` sha256 `{item['sha256']}`")
    if record.get("note"):
        lines.extend(["", f"Note: {record['note']}"])
    lines.extend(
        [
            "",
            "Operator instruction: send only this pointer text. Do not paste full contracts, patches, payloads, tokens, or raw logs into chat.",
            "Receiver instruction: inspect accepted quarantined files locally; keep auto_ingest=false and memory=off.",
        ]
    )
    return "\n".join(lines) + "\n"


def _source_record(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise SynapsValidationError(f"source file not found: {source.name}")
    data = source.read_bytes()
    return {"name": source.name, "size": len(data), "sha256": _sha256_bytes(data)}


def _safe_identifier(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(raw or "").strip())
    safe = safe.strip("-_")
    if not safe:
        raise SynapsValidationError("transfer id is required")
    return safe[:120]


def _safe_sha256(raw: str) -> str:
    value = str(raw or "").strip().lower()
    if not value:
        return ""
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise SynapsValidationError("patch sha256 must be 64 lowercase hex characters")
    return value


def _safe_text(raw: str, limit: int) -> str:
    text = " ".join(str(raw or "").replace("\r", " ").replace("\n", " ").split())
    return text[:limit]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
