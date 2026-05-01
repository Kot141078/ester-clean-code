"""Explicit Codex mailbox promotion for SYNAPS quarantine transfers.

This module never executes received files and never imports them into
memory/vector/RAG stores. It only validates a quarantined `codex_*`
file_manifest transfer and, when explicitly confirmed, copies it into a
dedicated inbox with a receipt ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .file_transfer import DEFAULT_QUARANTINE_ROOT, FileTransferPolicy, parse_file_manifest
from .protocol import SynapsValidationError


CODEX_MAILBOX_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_MAILBOX_PROMOTE"
CODEX_MAILBOX_RECEIPT_SCHEMA = "ester.synaps.codex_mailbox_receipt.v1"
DEFAULT_CODEX_MAILBOX_ROOT = Path("data") / "synaps" / "codex_bridge"
DEFAULT_CODEX_INBOX_ROOT = DEFAULT_CODEX_MAILBOX_ROOT / "inbox"
DEFAULT_CODEX_RECEIPT_LEDGER = DEFAULT_CODEX_MAILBOX_ROOT / "receipts" / "events.jsonl"
CODEX_MAILBOX_KINDS = frozenset({"codex_contract", "codex_report", "codex_patch", "codex_receipt"})
CODEX_MAILBOX_SUFFIXES = frozenset({".md", ".txt", ".patch", ".json"})


@dataclass(frozen=True)
class CodexMailboxPolicy:
    allowed_kinds: frozenset[str] = CODEX_MAILBOX_KINDS
    allowed_suffixes: frozenset[str] = CODEX_MAILBOX_SUFFIXES
    max_files: int = 5

    @classmethod
    def default(cls) -> "CodexMailboxPolicy":
        return cls()

    def to_record(self) -> dict[str, Any]:
        return {
            "allowed_kinds": sorted(self.allowed_kinds),
            "allowed_suffixes": sorted(self.allowed_suffixes),
            "max_files": self.max_files,
        }


def list_codex_mailbox_transfers(
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    inbox_root: str | Path = DEFAULT_CODEX_INBOX_ROOT,
    policy: CodexMailboxPolicy | None = None,
) -> dict[str, Any]:
    root = Path(quarantine_root)
    actual_policy = policy or CodexMailboxPolicy.default()
    transfers: list[dict[str, Any]] = []
    if root.exists():
        for item in sorted(root.iterdir(), key=lambda entry: entry.name):
            if not item.is_dir():
                continue
            try:
                record = inspect_codex_mailbox_transfer(item.name, root, inbox_root, actual_policy)
                transfers.append(_summary(record))
            except Exception as exc:
                transfers.append(
                    {
                        "transfer_id": item.name,
                        "ok": False,
                        "status": "invalid",
                        "problems": [f"{exc.__class__.__name__}: {exc}"],
                    }
                )
    return {
        "ok": True,
        "quarantine_root": str(root),
        "inbox_root": str(Path(inbox_root)),
        "policy": actual_policy.to_record(),
        "count": len(transfers),
        "transfers": transfers,
    }


def inspect_codex_mailbox_transfer(
    transfer_id: str,
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    inbox_root: str | Path = DEFAULT_CODEX_INBOX_ROOT,
    policy: CodexMailboxPolicy | None = None,
) -> dict[str, Any]:
    actual_policy = policy or CodexMailboxPolicy.default()
    qroot = Path(quarantine_root)
    transfer_name = _safe_identifier(transfer_id)
    transfer_dir = _ensure_under(qroot, qroot / transfer_name)
    manifest_path = transfer_dir / "manifest.json"
    files_dir = transfer_dir / "files"
    problems: list[str] = []
    files: list[dict[str, Any]] = []

    if not manifest_path.is_file():
        problems.append("manifest_missing")
        manifest: dict[str, Any] = {}
    else:
        try:
            manifest = parse_file_manifest(
                manifest_path.read_text(encoding="utf-8"),
                FileTransferPolicy(max_files=actual_policy.max_files),
            )
        except Exception as exc:
            manifest = {}
            problems.append(f"manifest_invalid:{exc.__class__.__name__}")

    manifest_transfer_id = str(manifest.get("transfer_id") or "")
    if manifest_transfer_id and manifest_transfer_id != transfer_name:
        problems.append("transfer_id_mismatch")

    for item in manifest.get("files") or []:
        file_record = _inspect_manifest_file(item, files_dir, actual_policy)
        files.append(file_record)
        problems.extend(file_record["problems"])

    if not files and manifest:
        problems.append("no_files")

    inbox_transfer_dir = _ensure_under(Path(inbox_root), Path(inbox_root) / transfer_name)
    promoted = inbox_transfer_dir.exists()
    status = "ready"
    if problems:
        status = "invalid"
    elif promoted:
        status = "already_promoted"

    return {
        "ok": not problems,
        "status": status,
        "transfer_id": transfer_name,
        "quarantine_path": str(transfer_dir),
        "manifest_path": str(manifest_path),
        "inbox_path": str(inbox_transfer_dir),
        "promoted": promoted,
        "auto_execute": False,
        "auto_ingest": False,
        "memory": "off",
        "manifest": _public_manifest_record(manifest),
        "files": files,
        "problems": problems,
        "policy": actual_policy.to_record(),
    }


def promote_codex_mailbox_transfer(
    transfer_id: str,
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    inbox_root: str | Path = DEFAULT_CODEX_INBOX_ROOT,
    receipt_ledger: str | Path = DEFAULT_CODEX_RECEIPT_LEDGER,
    *,
    apply: bool = False,
    confirm: str = "",
    operator: str = "codex",
    policy: CodexMailboxPolicy | None = None,
) -> dict[str, Any]:
    actual_policy = policy or CodexMailboxPolicy.default()
    inspection = inspect_codex_mailbox_transfer(transfer_id, quarantine_root, inbox_root, actual_policy)
    output: dict[str, Any] = {
        "ok": bool(inspection["ok"]),
        "dry_run": not apply,
        "action": "promote",
        "confirm_required": CODEX_MAILBOX_CONFIRM_PHRASE,
        "inspection": inspection,
    }
    if not inspection["ok"]:
        output["result"] = {"ok": False, "error": "inspection_failed", "problems": inspection["problems"]}
        return output
    if not apply:
        output["result"] = {
            "ok": True,
            "status": "would_promote",
            "writes": {
                "inbox_path": inspection["inbox_path"],
                "receipt_ledger": str(Path(receipt_ledger)),
            },
        }
        return output
    if confirm != CODEX_MAILBOX_CONFIRM_PHRASE:
        output["ok"] = False
        output["result"] = {"ok": False, "error": "promote_gate_failed", "problems": ["missing_confirm_phrase"]}
        return output
    if inspection["promoted"]:
        output["ok"] = False
        output["result"] = {"ok": False, "error": "promote_target_exists"}
        return output

    receipt = _copy_to_inbox(inspection, Path(inbox_root), Path(receipt_ledger), operator)
    output["result"] = {"ok": True, "status": "promoted", "receipt": receipt}
    return output


def _inspect_manifest_file(
    item: Mapping[str, Any],
    files_dir: Path,
    policy: CodexMailboxPolicy,
) -> dict[str, Any]:
    name = str(item.get("name") or "")
    kind = str(item.get("kind") or "")
    size = int(item.get("size") or 0)
    sha256 = str(item.get("sha256") or "").lower()
    stored_path = _ensure_under(files_dir, files_dir / name) if name else files_dir
    problems: list[str] = []

    if kind not in policy.allowed_kinds:
        problems.append(f"kind_not_allowed:{kind or '<missing>'}")
    if Path(name).suffix.lower() not in policy.allowed_suffixes:
        problems.append("suffix_not_allowed")
    if not stored_path.is_file():
        problems.append("stored_file_missing")
        actual_size: int | None = None
        actual_sha256: str | None = None
    else:
        actual_size = stored_path.stat().st_size
        actual_sha256 = _sha256_file(stored_path)
        if actual_size != size:
            problems.append("size_mismatch")
        if actual_sha256 != sha256:
            problems.append("sha256_mismatch")

    return {
        "name": name,
        "kind": kind,
        "size": size,
        "sha256": sha256,
        "path": str(stored_path),
        "actual_size": actual_size,
        "actual_sha256": actual_sha256,
        "ok": not problems,
        "problems": problems,
    }


def _copy_to_inbox(
    inspection: Mapping[str, Any],
    inbox_root: Path,
    receipt_ledger: Path,
    operator: str,
) -> dict[str, Any]:
    transfer_id = str(inspection["transfer_id"])
    target_dir = _ensure_under(inbox_root, inbox_root / transfer_id)
    tmp_dir = _ensure_under(inbox_root, inbox_root / f".{transfer_id}.tmp")
    if target_dir.exists() or tmp_dir.exists():
        raise SynapsValidationError("promote target already exists")
    files_target = tmp_dir / "files"
    files_target.mkdir(parents=True, exist_ok=False)

    copied_files: list[dict[str, Any]] = []
    for item in inspection["files"]:
        source = Path(str(item["path"]))
        relative_name = str(item["name"])
        target = _ensure_under(files_target, files_target / relative_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        copied_files.append(
            {
                "name": relative_name,
                "kind": str(item["kind"]),
                "size": int(item["size"]),
                "sha256": str(item["sha256"]),
            }
        )

    manifest_source = Path(str(inspection["manifest_path"]))
    (tmp_dir / "manifest.json").write_text(manifest_source.read_text(encoding="utf-8"), encoding="utf-8")
    receipt = {
        "schema": CODEX_MAILBOX_RECEIPT_SCHEMA,
        "event": "promoted",
        "created_at": _utc_now(),
        "transfer_id": transfer_id,
        "operator": _preview(operator, 120),
        "quarantine_path": str(inspection["quarantine_path"]),
        "inbox_path": str(target_dir),
        "file_count": len(copied_files),
        "files": copied_files,
        "auto_execute": False,
        "auto_ingest": False,
        "memory": "off",
    }
    (tmp_dir / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir.rename(target_dir)
    _append_jsonl(receipt_ledger, receipt)
    return receipt


def _summary(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "transfer_id": record.get("transfer_id"),
        "ok": record.get("ok"),
        "status": record.get("status"),
        "promoted": record.get("promoted"),
        "file_count": len(record.get("files") or []),
        "kinds": sorted({str(item.get("kind") or "") for item in record.get("files") or []}),
        "problems": list(record.get("problems") or []),
    }


def _public_manifest_record(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": manifest.get("schema"),
        "transfer_id": manifest.get("transfer_id"),
        "received_from": manifest.get("received_from"),
        "received_message_id": manifest.get("received_message_id"),
        "auto_ingest": manifest.get("auto_ingest"),
        "memory": manifest.get("memory"),
        "mode": manifest.get("mode"),
        "note": manifest.get("note"),
        "total_bytes": manifest.get("total_bytes"),
    }


def _safe_identifier(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(raw or "").strip())
    safe = safe.strip("-_")
    if not safe:
        raise SynapsValidationError("transfer_id is required")
    return safe[:120]


def _ensure_under(root: Path, target: Path) -> Path:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    try:
        target_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise SynapsValidationError("path escapes mailbox root") from exc
    return target_resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 64), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


def _preview(text: str, limit: int) -> str:
    compact = " ".join(str(text or "").split())
    return compact[:limit]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
