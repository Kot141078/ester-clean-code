"""Fail-closed operator gate for scheduled SYNAPS actions.

This layer coordinates conversation windows and file transfers without becoming
an always-on loop. It only records operator-approved real attempts and never
imports or mutates memory/vector/passport stores.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .protocol import SynapsValidationError


ACTION_CONVERSATION = "conversation"
ACTION_FILE_TRANSFER = "file_transfer"
DEFAULT_OPERATOR_GATE_LEDGER_ROOT = Path("data") / "synaps" / "operator_gate"
OPERATOR_GATE_CONFIRM_PHRASE = "ESTER_READY_FOR_SYNAPS_OPERATOR_GATE"
OPERATOR_GATE_MODE = "synaps_operator_gate"


@dataclass(frozen=True)
class OperatorGatePolicy:
    max_actions_per_tick: int = 1
    conversation_cooldown_sec: int = 60 * 60
    file_transfer_cooldown_sec: int = 60 * 60
    max_duration_sec: int = 15 * 60
    max_messages: int = 10
    max_files: int = 5
    max_file_bytes: int = 64 * 1024
    max_total_bytes: int = 128 * 1024

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "OperatorGatePolicy":
        source = os.environ if env is None else env
        return cls(
            max_actions_per_tick=_bounded_int(
                source.get("SISTER_OPERATOR_GATE_MAX_ACTIONS_PER_TICK"),
                default=1,
                minimum=1,
                maximum=1,
            ),
            conversation_cooldown_sec=_bounded_int(
                source.get("SISTER_CONVERSATION_WINDOW_COOLDOWN_SEC"),
                default=60 * 60,
                minimum=60 * 60,
                maximum=24 * 60 * 60,
            ),
            file_transfer_cooldown_sec=_bounded_int(
                source.get("SISTER_FILE_TRANSFER_COOLDOWN_SEC"),
                default=60 * 60,
                minimum=60 * 60,
                maximum=24 * 60 * 60,
            ),
            max_duration_sec=_bounded_int(
                source.get("SISTER_CONVERSATION_WINDOW_MAX_DURATION_SEC"),
                default=15 * 60,
                minimum=60,
                maximum=15 * 60,
            ),
            max_messages=_bounded_int(
                source.get("SISTER_CONVERSATION_WINDOW_MAX_MESSAGES"),
                default=10,
                minimum=1,
                maximum=10,
            ),
            max_files=_bounded_int(
                source.get("SISTER_FILE_TRANSFER_MAX_FILES"),
                default=5,
                minimum=1,
                maximum=10,
            ),
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
        )

    def to_record(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class OperatorGateDecision:
    action: str
    ok: bool
    problems: tuple[str, ...] = ()
    next_open_at: str = ""
    last_action_id: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "ok": self.ok,
            "problems": list(self.problems),
            "next_open_at": self.next_open_at,
            "last_action_id": self.last_action_id,
        }


class OperatorGateStore:
    """Append-only ledger for operator-approved SYNAPS scheduler attempts."""

    def __init__(self, root: str | Path = DEFAULT_OPERATOR_GATE_LEDGER_ROOT) -> None:
        root_path = Path(root)
        if not str(root_path).strip():
            raise SynapsValidationError("operator gate ledger root is required")
        self.root = root_path
        self.index_path = self.root / "events.jsonl"

    def can_run_file_transfer(
        self,
        policy: OperatorGatePolicy,
        now: datetime | None = None,
    ) -> OperatorGateDecision:
        current = _coerce_utc(now)
        latest = self._latest_counting_action(ACTION_FILE_TRANSFER)
        if not latest:
            return OperatorGateDecision(action=ACTION_FILE_TRANSFER, ok=True)

        created_at = _parse_utc(str(latest.get("created_at", "")))
        if created_at is None:
            return OperatorGateDecision(action=ACTION_FILE_TRANSFER, ok=True)

        next_open = created_at + timedelta(seconds=policy.file_transfer_cooldown_sec)
        if current < next_open:
            return OperatorGateDecision(
                action=ACTION_FILE_TRANSFER,
                ok=False,
                problems=("file_transfer_cooldown_active",),
                next_open_at=_iso(next_open),
                last_action_id=str(latest.get("action_id") or ""),
            )
        return OperatorGateDecision(action=ACTION_FILE_TRANSFER, ok=True)

    def record_action_result(
        self,
        *,
        action: str,
        action_id: str | None,
        ok: bool,
        status: int,
        summary: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        normalized_action = normalize_action(action)
        actual_action_id = _safe_identifier(action_id or f"synaps-operator-{uuid4()}")
        record = {
            "event": "action_finished",
            "mode": OPERATOR_GATE_MODE,
            "action": normalized_action,
            "action_id": actual_action_id,
            "created_at": _iso(_coerce_utc(now)),
            "ok": bool(ok),
            "status": int(status),
            "summary": dict(summary or {}),
        }
        self._append_jsonl(self.index_path, record)
        self._append_jsonl(self._action_events_path(actual_action_id), record)
        return record

    def _latest_counting_action(self, action: str) -> dict[str, Any] | None:
        if not self.index_path.is_file():
            return None

        latest: dict[str, Any] | None = None
        normalized_action = normalize_action(action)
        for line in self.index_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            if not isinstance(record, dict):
                continue
            if record.get("event") != "action_finished" or record.get("action") != normalized_action:
                continue
            latest = record
        return latest

    def _action_events_path(self, action_id: str) -> Path:
        return self.root / _safe_identifier(action_id) / "events.jsonl"

    def _append_jsonl(self, path: Path, record: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


def normalize_action(action: str) -> str:
    normalized = str(action or "").strip().lower().replace("-", "_")
    if normalized not in {ACTION_CONVERSATION, ACTION_FILE_TRANSFER}:
        raise SynapsValidationError(f"unknown operator action: {action}")
    return normalized


def normalize_actions(raw_action: str) -> tuple[str, ...]:
    normalized = str(raw_action or "").strip().lower().replace("-", "_")
    if normalized == "both":
        return (ACTION_CONVERSATION, ACTION_FILE_TRANSFER)
    return (normalize_action(normalized),)


def operator_gate_arm_status(env: Mapping[str, str]) -> dict[str, bool]:
    return {
        "operator_gate": _env_bool(env.get("SISTER_OPERATOR_GATE", "0")),
        "armed": _env_bool(env.get("SISTER_OPERATOR_GATE_ARMED", "0")),
        "kill_switch": _env_bool(env.get("SISTER_OPERATOR_KILL_SWITCH", "0"))
        or _env_bool(env.get("SYNAPS_OPERATOR_KILL_SWITCH", "0")),
        "legacy_autochat": _env_bool(env.get("SISTER_AUTOCHAT", "0")),
        "conversation_window": _env_bool(env.get("SISTER_CONVERSATION_WINDOW", "0")),
        "file_transfer": _env_bool(env.get("SISTER_FILE_TRANSFER", "0")),
    }


def validate_operator_gate_send_gate(
    env: Mapping[str, str],
    confirm: str,
    actions: Sequence[str],
    store: OperatorGateStore,
    policy: OperatorGatePolicy,
    now: datetime | None = None,
) -> list[str]:
    problems: list[str] = []
    status = operator_gate_arm_status(env)
    normalized_actions: list[str] = []

    for action in actions:
        try:
            normalized_actions.append(normalize_action(action))
        except SynapsValidationError:
            problems.append("unknown_operator_action")

    if confirm != OPERATOR_GATE_CONFIRM_PHRASE:
        problems.append("missing_operator_confirm_phrase")
    if not status["operator_gate"]:
        problems.append("SISTER_OPERATOR_GATE_not_enabled")
    if not status["armed"]:
        problems.append("SISTER_OPERATOR_GATE_ARMED_not_enabled")
    if status["kill_switch"]:
        problems.append("SISTER_OPERATOR_KILL_SWITCH_enabled")
    if status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    if not normalized_actions:
        problems.append("missing_operator_action")
    if len(normalized_actions) > policy.max_actions_per_tick:
        problems.append("operator_gate_allows_one_action_per_tick")

    if ACTION_FILE_TRANSFER in normalized_actions:
        file_gate = store.can_run_file_transfer(policy, now=now)
        if not file_gate.ok:
            problems.extend(file_gate.problems)

    return problems


def _bounded_int(raw: str | None, *, default: int, minimum: int, maximum: int) -> int:
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


def _parse_utc(raw: str) -> datetime | None:
    try:
        text = raw.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return _coerce_utc(datetime.fromisoformat(text))
    except Exception:
        return None


def _safe_identifier(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in raw.strip())
    safe = safe.strip("-_")
    return (safe or f"synaps-operator-{uuid4()}")[:120]
