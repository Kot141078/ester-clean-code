"""Fail-closed Codex request queue for sister-initiated work.

The queue lets Ester/Lii record bounded requests for a Codex operator. It does
not execute tasks, run shell commands, import files into memory/RAG/vector, or
start any daemon. Codex must explicitly inspect, claim, and complete requests.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .protocol import SynapsValidationError


CODEX_REQUEST_SCHEMA = "ester.synaps.codex_request.v1"
CODEX_REQUEST_EVENT_SCHEMA = "ester.synaps.codex_request_event.v1"
CODEX_REQUEST_CREATE_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_REQUEST_CREATE"
CODEX_REQUEST_CLAIM_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_REQUEST_CLAIM"
CODEX_REQUEST_COMPLETE_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_REQUEST_COMPLETE"
DEFAULT_CODEX_REQUEST_ROOT = Path("data") / "synaps" / "codex_bridge" / "requests"

REQUEST_STATUS_QUEUED = "queued"
REQUEST_STATUS_CLAIMED = "claimed"
REQUEST_STATUS_COMPLETED = "completed"
REQUEST_STATUS_BLOCKED = "blocked"

_PRIORITIES = {"low", "normal", "high"}
_COMPLETE_STATUSES = {REQUEST_STATUS_COMPLETED, REQUEST_STATUS_BLOCKED}


@dataclass(frozen=True)
class CodexRequestPolicy:
    max_title_chars: int = 160
    max_task_chars: int = 4000
    max_tags: int = 8
    max_related_transfers: int = 12
    max_summary_chars: int = 2000

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexRequestPolicy":
        source = os.environ if env is None else env
        return cls(
            max_title_chars=_bounded_int(source.get("SYNAPS_CODEX_REQUEST_MAX_TITLE_CHARS"), 160, 20, 240),
            max_task_chars=_bounded_int(source.get("SYNAPS_CODEX_REQUEST_MAX_TASK_CHARS"), 4000, 200, 8000),
            max_tags=_bounded_int(source.get("SYNAPS_CODEX_REQUEST_MAX_TAGS"), 8, 0, 16),
            max_related_transfers=_bounded_int(source.get("SYNAPS_CODEX_REQUEST_MAX_TRANSFERS"), 12, 0, 24),
            max_summary_chars=_bounded_int(source.get("SYNAPS_CODEX_REQUEST_MAX_SUMMARY_CHARS"), 2000, 40, 4000),
        )

    def to_record(self) -> dict[str, int]:
        return asdict(self)


class CodexRequestStore:
    """Append-only request ledger. State is derived from events."""

    def __init__(self, root: str | Path = DEFAULT_CODEX_REQUEST_ROOT, policy: CodexRequestPolicy | None = None) -> None:
        root_path = Path(root)
        if not str(root_path).strip():
            raise SynapsValidationError("codex request root is required")
        self.root = root_path
        self.policy = policy or CodexRequestPolicy()
        self.index_path = self.root / "events.jsonl"

    def build_request(
        self,
        *,
        title: str,
        task: str,
        requester: str,
        origin: str,
        priority: str = "normal",
        tags: Sequence[str] | None = None,
        related_transfer_ids: Sequence[str] | None = None,
        request_id: str | None = None,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        normalized_request_id = _safe_identifier(request_id or f"codex-req-{uuid4()}")
        normalized_title = _bounded_text(title, self.policy.max_title_chars, "title")
        normalized_task = _bounded_text(task, self.policy.max_task_chars, "task")
        normalized_priority = _normalize_priority(priority)
        normalized_tags = _normalize_tags(tags or (), self.policy)
        normalized_transfers = _normalize_transfer_ids(related_transfer_ids or (), self.policy)
        timestamp = _iso(_coerce_utc(created_at))

        return {
            "schema": CODEX_REQUEST_SCHEMA,
            "request_id": normalized_request_id,
            "created_at": timestamp,
            "requester": _preview(requester or "sister", 120),
            "origin": _preview(origin or "unknown", 120),
            "priority": normalized_priority,
            "title": normalized_title,
            "task": normalized_task,
            "task_sha256": _sha256_text(normalized_task),
            "tags": normalized_tags,
            "related_transfer_ids": normalized_transfers,
            "status": REQUEST_STATUS_QUEUED,
            "auto_execute": False,
            "auto_ingest": False,
            "memory": "off",
            "requires_codex_claim": True,
            "requires_operator_gate": True,
        }

    def create_request(self, request_record: Mapping[str, Any]) -> dict[str, Any]:
        request_id = _safe_identifier(str(request_record.get("request_id") or ""))
        request_dir = self._request_dir(request_id)
        if request_dir.exists():
            raise SynapsValidationError("codex request already exists")

        request_dir.mkdir(parents=True, exist_ok=False)
        request_path = request_dir / "request.json"
        record = dict(request_record)
        request_path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        event = self._event(
            request_id=request_id,
            event="created",
            actor=str(record.get("requester") or "sister"),
            status=REQUEST_STATUS_QUEUED,
            summary={"title": record.get("title"), "priority": record.get("priority")},
        )
        self._append_event(request_id, event)
        return self.inspect_request(request_id)

    def list_requests(self, status: str | None = None) -> dict[str, Any]:
        requests: list[dict[str, Any]] = []
        if self.root.exists():
            for item in sorted(self.root.iterdir(), key=lambda entry: entry.name):
                if item.is_dir() and (item / "request.json").is_file():
                    try:
                        record = self.inspect_request(item.name)
                    except Exception:
                        continue
                    if status and record.get("status") != status:
                        continue
                    requests.append(_summary(record))
        return {
            "ok": True,
            "root": str(self.root),
            "count": len(requests),
            "requests": requests,
            "auto_execute": False,
            "auto_ingest": False,
            "memory": "off",
        }

    def inspect_request(self, request_id: str) -> dict[str, Any]:
        safe_id = _safe_identifier(request_id)
        request_dir = self._request_dir(safe_id)
        request_path = request_dir / "request.json"
        if not request_path.is_file():
            raise SynapsValidationError("codex request not found")
        request_record = json.loads(request_path.read_text(encoding="utf-8"))
        events = self._read_events(safe_id)
        state = _state_from_events(events)
        return {
            "ok": True,
            "request": _public_request_record(request_record),
            "request_path": str(request_path),
            "events_path": str(request_dir / "events.jsonl"),
            "status": state["status"],
            "claimed_by": state.get("claimed_by", ""),
            "completed_by": state.get("completed_by", ""),
            "event_count": len(events),
            "events": events,
            "auto_execute": False,
            "auto_ingest": False,
            "memory": "off",
        }

    def claim_request(self, request_id: str, *, operator: str) -> dict[str, Any]:
        current = self.inspect_request(request_id)
        if current["status"] != REQUEST_STATUS_QUEUED:
            raise SynapsValidationError("codex request is not queued")
        safe_id = _safe_identifier(request_id)
        event = self._event(
            request_id=safe_id,
            event="claimed",
            actor=operator or "codex",
            status=REQUEST_STATUS_CLAIMED,
            summary={"claimed_by": _preview(operator or "codex", 120)},
        )
        self._append_event(safe_id, event)
        return self.inspect_request(safe_id)

    def complete_request(
        self,
        request_id: str,
        *,
        operator: str,
        summary: str,
        status: str = REQUEST_STATUS_COMPLETED,
    ) -> dict[str, Any]:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in _COMPLETE_STATUSES:
            raise SynapsValidationError("completion status must be completed or blocked")
        current = self.inspect_request(request_id)
        if current["status"] not in {REQUEST_STATUS_QUEUED, REQUEST_STATUS_CLAIMED}:
            raise SynapsValidationError("codex request is already closed")
        safe_id = _safe_identifier(request_id)
        event = self._event(
            request_id=safe_id,
            event=normalized_status,
            actor=operator or "codex",
            status=normalized_status,
            summary={
                "completed_by": _preview(operator or "codex", 120),
                "summary": _preview(summary, self.policy.max_summary_chars),
            },
        )
        self._append_event(safe_id, event)
        return self.inspect_request(safe_id)

    def _request_dir(self, request_id: str) -> Path:
        return _ensure_under(self.root, self.root / _safe_identifier(request_id))

    def _event(
        self,
        *,
        request_id: str,
        event: str,
        actor: str,
        status: str,
        summary: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema": CODEX_REQUEST_EVENT_SCHEMA,
            "event": event,
            "request_id": request_id,
            "created_at": _iso(_coerce_utc(None)),
            "actor": _preview(actor, 120),
            "status": status,
            "summary": dict(summary or {}),
            "auto_execute": False,
            "auto_ingest": False,
            "memory": "off",
        }

    def _append_event(self, request_id: str, event: Mapping[str, Any]) -> None:
        request_events_path = self._request_dir(request_id) / "events.jsonl"
        _append_jsonl(request_events_path, event)
        _append_jsonl(self.index_path, event)

    def _read_events(self, request_id: str) -> list[dict[str, Any]]:
        events_path = self._request_dir(request_id) / "events.jsonl"
        if not events_path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in events_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows


def codex_request_arm_status(env: Mapping[str, str]) -> dict[str, bool]:
    return {
        "requests": _env_bool(env.get("SYNAPS_CODEX_REQUESTS", "0")),
        "armed": _env_bool(env.get("SYNAPS_CODEX_REQUESTS_ARMED", "0")),
        "kill_switch": _env_bool(env.get("SYNAPS_CODEX_REQUESTS_KILL_SWITCH", "0"))
        or _env_bool(env.get("CODEX_REQUEST_KILL_SWITCH", "0")),
        "legacy_autochat": _env_bool(env.get("SISTER_AUTOCHAT", "0")),
    }


def validate_codex_request_gate(env: Mapping[str, str], confirm: str, expected_confirm: str) -> list[str]:
    status = codex_request_arm_status(env)
    problems: list[str] = []
    if confirm != expected_confirm:
        problems.append("missing_confirm_phrase")
    if not status["requests"]:
        problems.append("SYNAPS_CODEX_REQUESTS_not_enabled")
    if not status["armed"]:
        problems.append("SYNAPS_CODEX_REQUESTS_ARMED_not_enabled")
    if status["kill_switch"]:
        problems.append("SYNAPS_CODEX_REQUESTS_KILL_SWITCH_enabled")
    if status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    return problems


def _public_request_record(record: Mapping[str, Any]) -> dict[str, Any]:
    public = dict(record)
    public["auto_execute"] = False
    public["auto_ingest"] = False
    public["memory"] = "off"
    return public


def _summary(record: Mapping[str, Any]) -> dict[str, Any]:
    request = record.get("request") or {}
    if not isinstance(request, Mapping):
        request = {}
    return {
        "request_id": request.get("request_id"),
        "status": record.get("status"),
        "priority": request.get("priority"),
        "title": request.get("title"),
        "requester": request.get("requester"),
        "origin": request.get("origin"),
        "tags": list(request.get("tags") or []),
        "related_transfer_ids": list(request.get("related_transfer_ids") or []),
        "claimed_by": record.get("claimed_by", ""),
        "completed_by": record.get("completed_by", ""),
        "auto_execute": False,
        "auto_ingest": False,
        "memory": "off",
    }


def _state_from_events(events: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    status = REQUEST_STATUS_QUEUED
    claimed_by = ""
    completed_by = ""
    for event in events:
        event_name = str(event.get("event") or "")
        summary = event.get("summary") or {}
        if not isinstance(summary, Mapping):
            summary = {}
        if event_name == "claimed":
            status = REQUEST_STATUS_CLAIMED
            claimed_by = str(summary.get("claimed_by") or event.get("actor") or "")
        elif event_name in _COMPLETE_STATUSES:
            status = event_name
            completed_by = str(summary.get("completed_by") or event.get("actor") or "")
    return {"status": status, "claimed_by": claimed_by, "completed_by": completed_by}


def _normalize_priority(priority: str) -> str:
    value = str(priority or "normal").strip().lower()
    if value not in _PRIORITIES:
        raise SynapsValidationError("unknown codex request priority")
    return value


def _normalize_tags(tags: Sequence[str], policy: CodexRequestPolicy) -> list[str]:
    out: list[str] = []
    for raw in tags[: policy.max_tags]:
        tag = _safe_label(raw)
        if tag and tag not in out:
            out.append(tag)
    return out


def _normalize_transfer_ids(transfer_ids: Sequence[str], policy: CodexRequestPolicy) -> list[str]:
    out: list[str] = []
    for raw in transfer_ids[: policy.max_related_transfers]:
        value = _safe_identifier(raw)
        if not value.startswith("synaps-file-"):
            raise SynapsValidationError("related transfer id must start with synaps-file-")
        if value not in out:
            out.append(value)
    return out


def _bounded_text(value: str, limit: int, field: str) -> str:
    text = " ".join(str(value or "").replace("\r", "\n").split())
    if not text:
        raise SynapsValidationError(f"{field} is required")
    if len(text) > limit:
        raise SynapsValidationError(f"{field} exceeds policy")
    _reject_secret_like_text(text, field)
    return text


def _reject_secret_like_text(text: str, field: str) -> None:
    lowered = text.lower()
    forbidden = (
        "begin " + "private key",
        "sister_sync_token=",
        "api_key=",
        "password=",
        "authorization: bearer",
    )
    if any(marker in lowered for marker in forbidden):
        raise SynapsValidationError(f"{field} contains secret-like material")


def _safe_label(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(raw or "").strip().lower())
    safe = safe.strip("-_.")
    return safe[:64]


def _safe_identifier(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(raw or "").strip())
    safe = safe.strip("-_")
    if not safe:
        raise SynapsValidationError("identifier is required")
    return safe[:120]


def _ensure_under(root: Path, target: Path) -> Path:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    try:
        target_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise SynapsValidationError("path escapes codex request root") from exc
    return target_resolved


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


def _bounded_int(raw: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(raw if raw is not None else default).strip())
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _env_bool(raw: str) -> bool:
    return str(raw or "0").strip().lower() in {"1", "true", "yes", "on", "y", "enabled"}


def _coerce_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _coerce_utc(value).isoformat().replace("+00:00", "Z")


def _preview(text: str, limit: int) -> str:
    compact = " ".join(str(text or "").split())
    return compact[:limit]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()
