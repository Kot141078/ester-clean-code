"""Bounded SYNAPS Codex front-claim lease records.

This module provides a small metadata-only coordination primitive for Secretary
Codex instances. It does not run workers, schedulers, relay windows, or daemons.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from .codex_daemon import codex_daemon_arm_status
from .protocol import SynapsValidationError


CODEX_FRONT_CLAIM_SCHEMA = "ester.synaps.codex_front_claim.v1"
CODEX_FRONT_CLAIM_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_FRONT_CLAIM_WRITE"
CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_FRONT_CLAIM_CLOSE"
DEFAULT_CODEX_FRONT_CLAIM_ROOT = Path("data") / "synaps" / "codex_bridge" / "front_claims"
_ACTIVE_STATUSES = frozenset({"claimed", "accepted", "in_progress"})
_CLOSED_STATUSES = frozenset({"completed", "deferred", "failed", "released", "superseded"})
_STATUSES = _ACTIVE_STATUSES | _CLOSED_STATUSES


@dataclass(frozen=True)
class CodexFrontClaimPolicy:
    max_claim_bytes: int = 32 * 1024
    max_active_claims_per_front: int = 1

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexFrontClaimPolicy":
        source = os.environ if env is None else env
        return cls(
            max_claim_bytes=_bounded_int(source.get("SYNAPS_CODEX_FRONT_CLAIM_MAX_BYTES"), 32 * 1024, 1024, 128 * 1024),
            max_active_claims_per_front=_bounded_int(
                source.get("SYNAPS_CODEX_FRONT_CLAIM_MAX_ACTIVE_PER_FRONT"),
                1,
                1,
                3,
            ),
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def codex_front_claim_arm_status(env: Mapping[str, str]) -> dict[str, bool]:
    daemon = codex_daemon_arm_status(env)
    return {
        "claim": _env_bool(env.get("SYNAPS_CODEX_FRONT_CLAIM", "0")),
        "armed": _env_bool(env.get("SYNAPS_CODEX_FRONT_CLAIM_ARMED", "0")),
        "legacy_autochat": daemon["legacy_autochat"],
        "promote_mailbox": daemon["promote_mailbox"],
        "enqueue_handoffs": daemon["enqueue_handoffs"],
        "runner": daemon["runner"],
        "runner_armed": daemon["runner_armed"],
        "persistent": daemon["persistent"],
        "persistent_armed": daemon["persistent_armed"],
        "kill_switch": daemon["kill_switch"],
        "conversation_window": _env_bool(env.get("SISTER_CONVERSATION_WINDOW", "0")),
        "conversation_window_armed": _env_bool(env.get("SISTER_CONVERSATION_WINDOW_ARMED", "0")),
        "operator_gate": _env_bool(env.get("SISTER_OPERATOR_GATE", "0")),
        "operator_gate_armed": _env_bool(env.get("SISTER_OPERATOR_GATE_ARMED", "0")),
        "schedule": _env_bool(env.get("SISTER_SCHEDULE", "0")),
        "schedule_armed": _env_bool(env.get("SISTER_SCHEDULE_ARMED", "0")),
    }


def validate_codex_front_claim_gate(
    env: Mapping[str, str],
    *,
    apply: bool = False,
    confirm: str = "",
    operation: str = "write",
) -> list[str]:
    status = codex_front_claim_arm_status(env)
    problems: list[str] = []
    confirm_phrase = CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE if operation == "close" else CODEX_FRONT_CLAIM_CONFIRM_PHRASE
    if apply and confirm != confirm_phrase:
        problem = "missing_codex_front_claim_close_confirm_phrase" if operation == "close" else "missing_codex_front_claim_confirm_phrase"
        problems.append(problem)
    if apply and not status["claim"]:
        problems.append("SYNAPS_CODEX_FRONT_CLAIM_not_enabled")
    if apply and not status["armed"]:
        problems.append("SYNAPS_CODEX_FRONT_CLAIM_ARMED_not_enabled")
    if status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    if status["promote_mailbox"]:
        problems.append("SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX_must_remain_disabled")
    if status["enqueue_handoffs"]:
        problems.append("SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS_must_remain_disabled")
    if status["runner"] or status["runner_armed"]:
        problems.append("SYNAPS_CODEX_DAEMON_RUNNER_must_remain_disabled")
    if status["persistent"] or status["persistent_armed"]:
        problems.append("SYNAPS_CODEX_DAEMON_PERSISTENT_must_remain_disabled")
    if status["kill_switch"]:
        problems.append("SYNAPS_CODEX_DAEMON_KILL_SWITCH_enabled")
    for key in ("conversation_window", "conversation_window_armed", "operator_gate", "operator_gate_armed", "schedule", "schedule_armed"):
        if status[key]:
            problems.append(f"{key}_must_remain_disabled")
    return problems


def build_codex_front_claim(
    *,
    front_id: str,
    owner: str,
    marker: str,
    expected_report: Mapping[str, Any],
    status: str = "claimed",
    lease_seconds: int = 1800,
    title: str = "",
    supersedes: list[str] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    created = _parse_datetime(created_at) if created_at else datetime.now(timezone.utc)
    lease = _bounded_int(lease_seconds, 1800, 60, 24 * 3600)
    safe_front_id = _safe_token(front_id, "front_id", max_len=80)
    safe_owner = _safe_token(owner, "owner", max_len=80)
    safe_marker = str(marker or "").strip()[:240]
    if not safe_marker:
        raise SynapsValidationError("marker is required")
    claim = {
        "schema": CODEX_FRONT_CLAIM_SCHEMA,
        "claim_id": _claim_id(safe_front_id, safe_owner, safe_marker),
        "front_id": safe_front_id,
        "owner": safe_owner,
        "status": _safe_status(status),
        "title": str(title or "").strip()[:160],
        "marker": safe_marker,
        "created_at": created.isoformat(),
        "expires_at": (created + timedelta(seconds=lease)).isoformat(),
        "supersedes": _safe_supersedes(supersedes or []),
        "expected_report": _safe_expected_report(expected_report),
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
    }
    _validate_claim(claim)
    return claim


def write_codex_front_claim(
    claim: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    root: str | Path = DEFAULT_CODEX_FRONT_CLAIM_ROOT,
    apply: bool = False,
    confirm: str = "",
    operator: str = "codex-front-claim",
    policy: CodexFrontClaimPolicy | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    actual_env = dict(os.environ if env is None else env)
    actual_policy = policy or CodexFrontClaimPolicy.from_env(actual_env)
    safe_claim = _validate_claim(dict(claim))
    root_path = _safe_root(root)
    now_dt = now or datetime.now(timezone.utc)
    gate_problems = validate_codex_front_claim_gate(actual_env, apply=apply, confirm=confirm)
    conflict = _active_conflict(root_path, safe_claim, now_dt, actual_policy)
    output: dict[str, Any] = {
        "schema": CODEX_FRONT_CLAIM_SCHEMA,
        "ok": not gate_problems and not conflict,
        "dry_run": not apply,
        "confirm_required": CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
        "operator": _safe_token(operator, "operator", max_len=80),
        "claim": _claim_record(safe_claim),
        "policy": actual_policy.to_record(),
        "problems": [*gate_problems, *conflict],
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
    }
    if gate_problems:
        output["result"] = {"ok": False, "status": "front_claim_gate_failed", "problems": gate_problems}
        return output
    if conflict:
        output["result"] = {"ok": False, "status": "front_claim_conflict", "problems": conflict}
        return output
    if not apply:
        output["result"] = {"ok": True, "status": "would_write_front_claim"}
        return output

    claim_path = _claim_path(root_path, safe_claim)
    claim_text = _canonical_json(safe_claim)
    if len(claim_text.encode("utf-8")) > actual_policy.max_claim_bytes:
        output["ok"] = False
        output["problems"].append("front_claim_too_large")
        output["result"] = {"ok": False, "status": "front_claim_rejected", "problems": output["problems"]}
        return output
    if claim_path.exists():
        existing_text = claim_path.read_text(encoding="utf-8")
        if existing_text == claim_text:
            output["result"] = {"ok": True, "status": "front_claim_already_written"}
            output["path"] = str(claim_path)
            return output
        output["ok"] = False
        output["problems"].append("front_claim_id_collision")
        output["result"] = {"ok": False, "status": "front_claim_rejected", "problems": output["problems"]}
        return output

    claim_path.parent.mkdir(parents=True, exist_ok=True)
    claim_path.write_text(claim_text, encoding="utf-8", newline="\n")
    _append_event(root_path / "events.jsonl", {"event": "front_claim_written", "operator": output["operator"], "claim": _claim_record(safe_claim)})
    output["path"] = str(claim_path)
    output["result"] = {"ok": True, "status": "front_claim_written"}
    return output


def close_codex_front_claim(
    claim_id: str,
    *,
    status: str = "completed",
    reason: str = "",
    env: Mapping[str, str] | None = None,
    root: str | Path = DEFAULT_CODEX_FRONT_CLAIM_ROOT,
    apply: bool = False,
    confirm: str = "",
    operator: str = "codex-front-claim",
    policy: CodexFrontClaimPolicy | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    actual_env = dict(os.environ if env is None else env)
    actual_policy = policy or CodexFrontClaimPolicy.from_env(actual_env)
    safe_claim_id = _safe_token(claim_id, "claim_id", max_len=140)
    close_status = _safe_closed_status(status)
    root_path = _safe_root(root)
    claim_path = root_path / "claims" / f"{safe_claim_id}.json"
    gate_problems = validate_codex_front_claim_gate(actual_env, apply=apply, confirm=confirm, operation="close")
    output: dict[str, Any] = {
        "schema": CODEX_FRONT_CLAIM_SCHEMA,
        "ok": not gate_problems,
        "dry_run": not apply,
        "confirm_required": CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE,
        "operator": _safe_token(operator, "operator", max_len=80),
        "claim_id": safe_claim_id,
        "policy": actual_policy.to_record(),
        "problems": list(gate_problems),
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
    }
    if gate_problems:
        output["result"] = {"ok": False, "status": "front_claim_close_gate_failed", "problems": gate_problems}
        return output
    if not claim_path.exists():
        output["ok"] = False
        output["problems"].append("front_claim_not_found")
        output["result"] = {"ok": False, "status": "front_claim_not_found", "problems": output["problems"]}
        return output

    claim = _validate_claim(json.loads(claim_path.read_text(encoding="utf-8")))
    output["claim"] = _claim_record(claim)
    output["path"] = str(claim_path)
    if claim.get("status") not in _ACTIVE_STATUSES:
        output["result"] = {"ok": True, "status": "front_claim_already_closed"}
        return output
    if not apply:
        output["result"] = {"ok": True, "status": "would_close_front_claim", "close_status": close_status}
        return output

    closed = dict(claim)
    closed["previous_status"] = closed["status"]
    closed["status"] = close_status
    closed["closed_at"] = (now or datetime.now(timezone.utc)).isoformat()
    closed["closed_by"] = output["operator"]
    closed["close_reason"] = _safe_reason(reason)
    closed = _validate_claim(closed)
    claim_text = _canonical_json(closed)
    if len(claim_text.encode("utf-8")) > actual_policy.max_claim_bytes:
        output["ok"] = False
        output["problems"].append("front_claim_too_large")
        output["result"] = {"ok": False, "status": "front_claim_close_rejected", "problems": output["problems"]}
        return output

    claim_path.write_text(claim_text, encoding="utf-8", newline="\n")
    _append_event(
        root_path / "events.jsonl",
        {"event": "front_claim_closed", "operator": output["operator"], "claim": _claim_record(closed)},
    )
    output["claim"] = _claim_record(closed)
    output["result"] = {"ok": True, "status": "front_claim_closed", "close_status": close_status}
    return output


def list_codex_front_claims(root: str | Path = DEFAULT_CODEX_FRONT_CLAIM_ROOT, *, now: datetime | None = None) -> dict[str, Any]:
    root_path = _safe_root(root)
    now_dt = now or datetime.now(timezone.utc)
    claims = _load_claims(root_path)
    active = [claim for claim in claims if _is_active(claim, now_dt)]
    return {
        "schema": CODEX_FRONT_CLAIM_SCHEMA,
        "ok": True,
        "root": str(root_path),
        "claim_count": len(claims),
        "active_count": len(active),
        "claims": [_claim_record(claim) for claim in claims],
        "active": [_claim_record(claim) for claim in active],
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
    }


def _active_conflict(root: Path, claim: Mapping[str, Any], now: datetime, policy: CodexFrontClaimPolicy) -> list[str]:
    if claim["status"] not in _ACTIVE_STATUSES:
        return []
    supersedes = set(claim.get("supersedes") or [])
    active = [
        item
        for item in _load_claims(root)
        if item.get("front_id") == claim["front_id"]
        and item.get("claim_id") != claim["claim_id"]
        and _is_active(item, now)
        and item.get("claim_id") not in supersedes
    ]
    if len(active) >= policy.max_active_claims_per_front:
        ids = ",".join(str(item.get("claim_id")) for item in active[:3])
        return [f"active_front_claim_conflict:{ids}"]
    return []


def _load_claims(root: Path) -> list[dict[str, Any]]:
    claim_root = root / "claims"
    if not claim_root.exists():
        return []
    claims: list[dict[str, Any]] = []
    for path in sorted(claim_root.glob("*.json")):
        try:
            if path.stat().st_size > 128 * 1024:
                continue
            claims.append(_validate_claim(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return claims


def _validate_claim(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("schema") != CODEX_FRONT_CLAIM_SCHEMA:
        raise SynapsValidationError("unsupported front claim schema")
    raw["front_id"] = _safe_token(raw.get("front_id"), "front_id", max_len=80)
    raw["owner"] = _safe_token(raw.get("owner"), "owner", max_len=80)
    raw["status"] = _safe_status(str(raw.get("status") or ""))
    raw["claim_id"] = _safe_token(raw.get("claim_id"), "claim_id", max_len=140)
    raw["marker"] = str(raw.get("marker") or "").strip()[:240]
    if not raw["marker"]:
        raise SynapsValidationError("marker is required")
    _parse_datetime(raw.get("created_at"))
    _parse_datetime(raw.get("expires_at"))
    raw["supersedes"] = _safe_supersedes(raw.get("supersedes") or [])
    raw["expected_report"] = _safe_expected_report(raw.get("expected_report") or {})
    if raw.get("closed_at"):
        raw["closed_at"] = _parse_datetime(raw.get("closed_at")).isoformat()
    raw["closed_by"] = _safe_token(raw.get("closed_by"), "closed_by", max_len=80) if str(raw.get("closed_by") or "").strip() else ""
    raw["close_reason"] = _safe_reason(raw.get("close_reason", ""))
    raw["previous_status"] = _safe_status(raw["previous_status"]) if str(raw.get("previous_status") or "").strip() else ""
    raw["auto_ingest"] = False
    raw["memory"] = "off"
    raw["persistent"] = False
    return raw


def _safe_expected_report(raw: Mapping[str, Any]) -> dict[str, Any]:
    name = str(raw.get("name") or "").strip()
    if not name or Path(name).name != name:
        raise SynapsValidationError("expected report name is required")
    sha = str(raw.get("sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise SynapsValidationError("expected report sha256 is required")
    size = max(0, int(raw.get("size") or 0))
    if size <= 0:
        raise SynapsValidationError("expected report size is required")
    return {
        "name": name[:240],
        "sha256": sha,
        "size": size,
        "sender": str(raw.get("sender") or "").strip()[:120],
        "note_contains": str(raw.get("note_contains") or "").strip()[:240],
        "kind": str(raw.get("kind") or "codex_report").strip()[:80],
    }


def _is_active(claim: Mapping[str, Any], now: datetime) -> bool:
    if claim.get("status") not in _ACTIVE_STATUSES:
        return False
    try:
        return _parse_datetime(claim.get("expires_at")) > now
    except Exception:
        return False


def _claim_record(claim: Mapping[str, Any]) -> dict[str, Any]:
    record = {
        "claim_id": claim.get("claim_id"),
        "front_id": claim.get("front_id"),
        "owner": claim.get("owner"),
        "status": claim.get("status"),
        "marker": claim.get("marker"),
        "expires_at": claim.get("expires_at"),
        "supersedes": list(claim.get("supersedes") or []),
        "expected_report": dict(claim.get("expected_report") or {}),
    }
    for key in ("closed_at", "closed_by", "close_reason", "previous_status"):
        if claim.get(key):
            record[key] = claim.get(key)
    return record


def _claim_id(front_id: str, owner: str, marker: str) -> str:
    digest = hashlib.sha256(f"{front_id}\n{owner}\n{marker}".encode("utf-8")).hexdigest()[:12]
    return f"{front_id}__{owner}__{digest}"


def _claim_path(root: Path, claim: Mapping[str, Any]) -> Path:
    return root / "claims" / f"{claim['claim_id']}.json"


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _append_event(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"created_at": datetime.now(timezone.utc).isoformat(), **dict(record)}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _safe_root(raw: str | Path) -> Path:
    path = Path(raw)
    if path.exists() and path.is_symlink():
        raise SynapsValidationError("front claim root symlink rejected")
    return path.resolve()


def _safe_token(raw: Any, field: str, *, max_len: int) -> str:
    value = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(raw or "").strip()).strip("-_")
    if not value:
        raise SynapsValidationError(f"{field} is required")
    return value[:max_len]


def _safe_status(raw: str) -> str:
    status = str(raw or "").strip().lower()
    if status not in _STATUSES:
        raise SynapsValidationError("unsupported front claim status")
    return status


def _safe_closed_status(raw: str) -> str:
    status = _safe_status(raw)
    if status in _ACTIVE_STATUSES:
        raise SynapsValidationError("front claim close status must be inactive")
    return status


def _safe_reason(raw: Any) -> str:
    return str(raw or "").strip()[:240]


def _safe_supersedes(raw: list[str]) -> list[str]:
    return [_safe_token(item, "supersedes", max_len=140) for item in list(raw or [])[:8] if str(item or "").strip()]


def _parse_datetime(raw: Any) -> datetime:
    value = str(raw or "").strip()
    if not value:
        raise SynapsValidationError("timestamp is required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise SynapsValidationError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _env_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))
