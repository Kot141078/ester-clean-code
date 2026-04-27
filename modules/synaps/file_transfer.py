"""SYNAPS file/log transfer contracts with quarantine-only inbound storage."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .protocol import (
    SynapsConfig,
    SynapsEnvelope,
    SynapsMessageType,
    SynapsPreparedRequest,
    SynapsValidationError,
    build_envelope,
    prepare_outbound_request,
)


FILE_MANIFEST_SCHEMA = "ester.synaps.file_manifest.v1"
FILE_TRANSFER_CONFIRM_PHRASE = "ESTER_READY_FOR_FILE_TRANSFER_MANIFEST"
FILE_TRANSFER_MODE = "synaps_file_transfer"
DEFAULT_QUARANTINE_ROOT = Path("data") / "synaps" / "quarantine"


@dataclass(frozen=True)
class FileTransferPolicy:
    max_files: int = 5
    max_file_bytes: int = 64 * 1024
    max_total_bytes: int = 128 * 1024
    max_note_chars: int = 400

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "FileTransferPolicy":
        source = os.environ if env is None else env
        return cls(
            max_files=_bounded_int(source.get("SISTER_FILE_TRANSFER_MAX_FILES"), default=5, minimum=1, maximum=10),
            max_file_bytes=_bounded_int(
                source.get("SISTER_FILE_TRANSFER_MAX_FILE_BYTES"),
                default=64 * 1024,
                minimum=1,
                maximum=256 * 1024,
            ),
            max_total_bytes=_bounded_int(
                source.get("SISTER_FILE_TRANSFER_MAX_TOTAL_BYTES"),
                default=128 * 1024,
                minimum=1,
                maximum=512 * 1024,
            ),
            max_note_chars=_bounded_int(
                source.get("SISTER_FILE_TRANSFER_MAX_NOTE_CHARS"),
                default=400,
                minimum=0,
                maximum=1200,
            ),
        )

    def to_record(self) -> dict[str, int]:
        return asdict(self)


class SynapsQuarantineStore:
    """Append-only quarantine target; never imports or mutates memory/vector stores."""

    def __init__(self, root: str | Path = DEFAULT_QUARANTINE_ROOT, policy: FileTransferPolicy | None = None) -> None:
        self.root = Path(root)
        self.policy = policy or FileTransferPolicy()
        if not str(self.root).strip():
            raise SynapsValidationError("quarantine root is required")

    def receive_manifest(self, envelope: SynapsEnvelope) -> dict[str, Any]:
        manifest = parse_file_manifest(envelope.content, self.policy)
        transfer_id = _safe_identifier(str(manifest.get("transfer_id") or f"synaps-file-{uuid4()}"))
        transfer_dir = self.root / transfer_id
        if transfer_dir.exists():
            raise SynapsValidationError("transfer_id already exists in quarantine")

        files_dir = transfer_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=False)
        written_count = 0
        sanitized_manifest = _manifest_without_payload(manifest)
        sanitized_manifest["received_from"] = envelope.sender
        sanitized_manifest["received_message_id"] = envelope.message_id
        sanitized_manifest["auto_ingest"] = False
        sanitized_manifest["memory"] = "off"

        for item in manifest["files"]:
            if item.get("payload_encoding") != "base64" or not item.get("payload_b64"):
                continue
            rel_name = _validate_relative_name(str(item["name"]))
            target = _ensure_under(files_dir, files_dir / rel_name)
            payload = _decode_payload(str(item["payload_b64"]))
            if len(payload) != int(item["size"]):
                raise SynapsValidationError("payload size mismatch")
            if _sha256_bytes(payload) != str(item["sha256"]):
                raise SynapsValidationError("payload sha256 mismatch")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            written_count += 1

        (transfer_dir / "manifest.json").write_text(
            json.dumps(sanitized_manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        _append_jsonl(
            transfer_dir / "events.jsonl",
            {
                "event": "received",
                "created_at": _utc_now(),
                "sender": envelope.sender,
                "message_id": envelope.message_id,
                "file_count": len(manifest["files"]),
                "written_count": written_count,
                "auto_ingest": False,
                "memory": "off",
            },
        )
        return {
            "status": "quarantined" if written_count else "manifest_received",
            "transfer_id": transfer_id,
            "file_count": len(manifest["files"]),
            "written_count": written_count,
            "auto_ingest": False,
            "memory": "off",
        }


def build_file_manifest(
    file_paths: Sequence[str | Path],
    policy: FileTransferPolicy | None = None,
    *,
    include_payload: bool = False,
    base_dir: str | Path | None = None,
    transfer_id: str | None = None,
    kind: str = "file",
    note: str = "",
) -> dict[str, Any]:
    actual_policy = policy or FileTransferPolicy()
    if not file_paths:
        raise SynapsValidationError("at least one file is required")
    if len(file_paths) > actual_policy.max_files:
        raise SynapsValidationError("too many files for transfer policy")

    base = Path(base_dir).resolve() if base_dir else None
    files: list[dict[str, Any]] = []
    total_bytes = 0
    for raw_path in file_paths:
        source = Path(raw_path).resolve()
        if not source.is_file():
            raise SynapsValidationError(f"file not found: {Path(raw_path).name}")
        size = source.stat().st_size
        if size > actual_policy.max_file_bytes:
            raise SynapsValidationError("file exceeds per-file transfer policy")
        total_bytes += size
        if total_bytes > actual_policy.max_total_bytes:
            raise SynapsValidationError("files exceed total transfer policy")

        name = _manifest_name(source, base)
        record: dict[str, Any] = {
            "name": name,
            "kind": _safe_kind(kind),
            "size": size,
            "sha256": _sha256_file(source),
            "payload_encoding": "none",
        }
        if include_payload:
            payload = source.read_bytes()
            record["payload_encoding"] = "base64"
            record["payload_b64"] = base64.b64encode(payload).decode("ascii")
        files.append(record)

    return {
        "schema": FILE_MANIFEST_SCHEMA,
        "transfer_id": _safe_identifier(transfer_id or f"synaps-file-{uuid4()}"),
        "created_at": _utc_now(),
        "mode": "inline_quarantine" if include_payload else "manifest_only",
        "auto_ingest": False,
        "memory": "off",
        "note": _preview(note, actual_policy.max_note_chars),
        "total_bytes": total_bytes,
        "files": files,
    }


def build_file_manifest_request(config: SynapsConfig, manifest: Mapping[str, Any]) -> SynapsPreparedRequest:
    content = json.dumps(dict(manifest), ensure_ascii=False, sort_keys=True)
    envelope = build_envelope(
        config,
        content,
        SynapsMessageType.FILE_MANIFEST,
        metadata={
            "auto_ingest": False,
            "files": str(manifest.get("mode") or "manifest_only"),
            "memory": "off",
            "mode": FILE_TRANSFER_MODE,
            "operator_window": True,
            "transfer_id": str(manifest.get("transfer_id") or ""),
            "file_count": len(manifest.get("files") or []),
        },
    )
    return prepare_outbound_request(config, envelope, timeout_sec=config.timeout_sec)


def handle_synaps_file_manifest(
    envelope: SynapsEnvelope,
    root: str | Path = DEFAULT_QUARANTINE_ROOT,
    policy: FileTransferPolicy | None = None,
) -> dict[str, Any]:
    return SynapsQuarantineStore(root, policy).receive_manifest(envelope)


def parse_file_manifest(content: str, policy: FileTransferPolicy | None = None) -> dict[str, Any]:
    actual_policy = policy or FileTransferPolicy()
    try:
        manifest = json.loads(content)
    except Exception as exc:
        raise SynapsValidationError("file manifest is not valid json") from exc
    if not isinstance(manifest, Mapping):
        raise SynapsValidationError("file manifest must be an object")
    if manifest.get("schema") != FILE_MANIFEST_SCHEMA:
        raise SynapsValidationError("unsupported file manifest schema")
    if manifest.get("auto_ingest") is not False:
        raise SynapsValidationError("file manifest must disable auto_ingest")
    if str(manifest.get("memory") or "") != "off":
        raise SynapsValidationError("file manifest must set memory=off")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise SynapsValidationError("file manifest requires files")
    if len(files) > actual_policy.max_files:
        raise SynapsValidationError("too many files for transfer policy")

    total = 0
    normalized_files: list[dict[str, Any]] = []
    for raw_item in files:
        if not isinstance(raw_item, Mapping):
            raise SynapsValidationError("file manifest item must be an object")
        item = dict(raw_item)
        item["name"] = _validate_relative_name(str(item.get("name") or ""))
        item["size"] = _coerce_non_negative_int(item.get("size"))
        item["sha256"] = _validate_sha256(str(item.get("sha256") or ""))
        encoding = str(item.get("payload_encoding") or "none")
        if encoding not in {"none", "base64"}:
            raise SynapsValidationError("unsupported payload encoding")
        if encoding == "base64" and not item.get("payload_b64"):
            raise SynapsValidationError("missing base64 payload")
        if encoding == "none":
            item.pop("payload_b64", None)
        item["payload_encoding"] = encoding
        if item["size"] > actual_policy.max_file_bytes:
            raise SynapsValidationError("file exceeds per-file transfer policy")
        total += int(item["size"])
        if total > actual_policy.max_total_bytes:
            raise SynapsValidationError("files exceed total transfer policy")
        normalized_files.append(item)

    out = dict(manifest)
    out["transfer_id"] = _safe_identifier(str(out.get("transfer_id") or f"synaps-file-{uuid4()}"))
    out["files"] = normalized_files
    out["auto_ingest"] = False
    out["memory"] = "off"
    out["total_bytes"] = total
    return out


def file_transfer_arm_status(env: Mapping[str, str]) -> dict[str, bool]:
    return {
        "file_transfer": _env_bool(env.get("SISTER_FILE_TRANSFER", "0")),
        "armed": _env_bool(env.get("SISTER_FILE_TRANSFER_ARMED", "0")),
        "legacy_autochat": _env_bool(env.get("SISTER_AUTOCHAT", "0")),
        "conversation_window": _env_bool(env.get("SISTER_CONVERSATION_WINDOW", "0")),
    }


def validate_file_transfer_send_gate(env: Mapping[str, str], confirm: str) -> list[str]:
    problems: list[str] = []
    status = file_transfer_arm_status(env)
    if confirm != FILE_TRANSFER_CONFIRM_PHRASE:
        problems.append("missing_confirm_phrase")
    if not status["file_transfer"]:
        problems.append("SISTER_FILE_TRANSFER_not_enabled")
    if not status["armed"]:
        problems.append("SISTER_FILE_TRANSFER_ARMED_not_enabled")
    if status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    if status["conversation_window"]:
        problems.append("SISTER_CONVERSATION_WINDOW_must_remain_disabled")
    return problems


def _manifest_without_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(manifest)
    files: list[dict[str, Any]] = []
    for item in out.get("files") or []:
        if isinstance(item, Mapping):
            clean = dict(item)
            if "payload_b64" in clean:
                clean["payload_b64"] = "<quarantined>"
            files.append(clean)
    out["files"] = files
    return out


def _manifest_name(source: Path, base: Path | None) -> str:
    if base is not None:
        try:
            name = str(source.relative_to(base))
        except ValueError as exc:
            raise SynapsValidationError("file is outside base-dir") from exc
    else:
        name = source.name
    return _validate_relative_name(name)


def _validate_relative_name(raw_name: str) -> str:
    normalized = raw_name.replace("\\", "/").strip()
    if not normalized or normalized.startswith("/") or ":" in normalized:
        raise SynapsValidationError("unsafe file name")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise SynapsValidationError("unsafe file name")
    return "/".join(_safe_path_part(part) for part in parts)


def _safe_path_part(part: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in part)
    if not safe or safe in {".", ".."}:
        raise SynapsValidationError("unsafe file name")
    return safe[:120]


def _safe_identifier(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in raw.strip())
    safe = safe.strip("-_")
    return (safe or f"synaps-file-{uuid4()}")[:120]


def _safe_kind(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(raw or "file"))
    return (safe or "file")[:40]


def _ensure_under(root: Path, target: Path) -> Path:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    try:
        target_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise SynapsValidationError("target escapes quarantine root") from exc
    return target_resolved


def _decode_payload(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except Exception as exc:
        raise SynapsValidationError("invalid base64 payload") from exc


def _validate_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise SynapsValidationError("invalid sha256")
    return normalized


def _coerce_non_negative_int(value: Any) -> int:
    try:
        number = int(value)
    except Exception as exc:
        raise SynapsValidationError("invalid file size") from exc
    if number < 0:
        raise SynapsValidationError("invalid file size")
    return number


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 64), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


def _bounded_int(raw: str | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(raw if raw is not None else default).strip())
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _env_bool(raw: str) -> bool:
    return str(raw or "0").strip().lower() in {"1", "true", "yes", "on", "y"}


def _preview(text: str, limit: int) -> str:
    compact = " ".join(str(text or "").split())
    if limit <= 0:
        return ""
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)] + "..."


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
