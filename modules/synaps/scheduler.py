"""Fail-closed scheduler tick for bounded SYNAPS actions.

This module is intentionally small and side-effect free until a caller records
an explicit tick result. It does not start a daemon and does not touch memory,
passport, vector, chroma, or RAG stores.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .operator_gate import ACTION_CONVERSATION, ACTION_FILE_TRANSFER, normalize_action
from .protocol import SynapsValidationError


DEFAULT_SCHEDULER_LEDGER_ROOT = Path("data") / "synaps" / "scheduler"
SCHEDULER_CONFIRM_PHRASE = "ESTER_READY_FOR_SYNAPS_SCHEDULE_TICK"
SCHEDULER_MODE = "synaps_schedule_tick"


@dataclass(frozen=True)
class SchedulerPolicy:
    interval_sec: int = 60 * 60
    max_actions_per_tick: int = 1
    allow_file_transfer: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "SchedulerPolicy":
        source = os.environ if env is None else env
        return cls(
            interval_sec=_bounded_int(
                source.get("SISTER_SCHEDULE_INTERVAL_SEC"),
                default=60 * 60,
                minimum=60 * 60,
                maximum=24 * 60 * 60,
            ),
            max_actions_per_tick=_bounded_int(
                source.get("SISTER_SCHEDULE_MAX_ACTIONS_PER_TICK"),
                default=1,
                minimum=1,
                maximum=1,
            ),
            allow_file_transfer=_env_bool(source.get("SISTER_SCHEDULE_ALLOW_FILE_TRANSFER", "0")),
        )

    def to_record(self) -> dict[str, int | bool]:
        return asdict(self)


@dataclass(frozen=True)
class SchedulerTickDecision:
    action: str
    ok: bool
    problems: tuple[str, ...] = ()
    next_tick_at: str = ""
    last_tick_id: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "ok": self.ok,
            "problems": list(self.problems),
            "next_tick_at": self.next_tick_at,
            "last_tick_id": self.last_tick_id,
        }


class SchedulerTickStore:
    """Append-only ledger for real scheduler-approved attempts."""

    def __init__(self, root: str | Path = DEFAULT_SCHEDULER_LEDGER_ROOT) -> None:
        root_path = Path(root)
        if not str(root_path).strip():
            raise SynapsValidationError("scheduler ledger root is required")
        self.root = root_path
        self.index_path = self.root / "events.jsonl"

    def can_run(
        self,
        action: str,
        policy: SchedulerPolicy,
        now: datetime | None = None,
    ) -> SchedulerTickDecision:
        normalized_action = normalize_action(action)
        current = _coerce_utc(now)
        latest = self._latest_tick(normalized_action)
        if not latest:
            return SchedulerTickDecision(action=normalized_action, ok=True)

        created_at = _parse_utc(str(latest.get("created_at", "")))
        if created_at is None:
            return SchedulerTickDecision(action=normalized_action, ok=True)

        next_tick = created_at + timedelta(seconds=policy.interval_sec)
        if current < next_tick:
            return SchedulerTickDecision(
                action=normalized_action,
                ok=False,
                problems=("schedule_interval_active",),
                next_tick_at=_iso(next_tick),
                last_tick_id=str(latest.get("tick_id") or ""),
            )
        return SchedulerTickDecision(action=normalized_action, ok=True)

    def record_tick_result(
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
        tick_id = _safe_identifier(action_id or f"synaps-schedule-{uuid4()}")
        record = {
            "event": "tick_finished",
            "mode": SCHEDULER_MODE,
            "action": normalized_action,
            "tick_id": tick_id,
            "created_at": _iso(_coerce_utc(now)),
            "ok": bool(ok),
            "status": int(status),
            "summary": dict(summary or {}),
        }
        self._append_jsonl(self.index_path, record)
        self._append_jsonl(self.root / tick_id / "events.jsonl", record)
        return record

    def _latest_tick(self, action: str) -> dict[str, Any] | None:
        if not self.index_path.is_file():
            return None

        latest: dict[str, Any] | None = None
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
            if record.get("event") != "tick_finished" or record.get("action") != action:
                continue
            latest = record
        return latest

    def _append_jsonl(self, path: Path, record: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


def scheduler_arm_status(env: Mapping[str, str]) -> dict[str, bool]:
    return {
        "schedule": _env_bool(env.get("SISTER_SCHEDULE", "0")),
        "armed": _env_bool(env.get("SISTER_SCHEDULE_ARMED", "0")),
        "kill_switch": _env_bool(env.get("SISTER_SCHEDULE_KILL_SWITCH", "0"))
        or _env_bool(env.get("SYNAPS_SCHEDULE_KILL_SWITCH", "0")),
        "legacy_autochat": _env_bool(env.get("SISTER_AUTOCHAT", "0")),
        "operator_gate": _env_bool(env.get("SISTER_OPERATOR_GATE", "0")),
        "conversation_window": _env_bool(env.get("SISTER_CONVERSATION_WINDOW", "0")),
        "file_transfer": _env_bool(env.get("SISTER_FILE_TRANSFER", "0")),
    }


def validate_scheduler_send_gate(
    env: Mapping[str, str],
    confirm: str,
    actions: Sequence[str],
    store: SchedulerTickStore,
    policy: SchedulerPolicy,
    now: datetime | None = None,
) -> list[str]:
    problems: list[str] = []
    status = scheduler_arm_status(env)
    normalized_actions: list[str] = []

    for action in actions:
        try:
            normalized_actions.append(normalize_action(action))
        except SynapsValidationError:
            problems.append("unknown_scheduler_action")

    if confirm != SCHEDULER_CONFIRM_PHRASE:
        problems.append("missing_schedule_confirm_phrase")
    if not status["schedule"]:
        problems.append("SISTER_SCHEDULE_not_enabled")
    if not status["armed"]:
        problems.append("SISTER_SCHEDULE_ARMED_not_enabled")
    if status["kill_switch"]:
        problems.append("SISTER_SCHEDULE_KILL_SWITCH_enabled")
    if status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    if not normalized_actions:
        problems.append("missing_scheduler_action")
    if len(normalized_actions) > policy.max_actions_per_tick:
        problems.append("scheduler_allows_one_action_per_tick")
    if ACTION_FILE_TRANSFER in normalized_actions and not policy.allow_file_transfer:
        problems.append("SISTER_SCHEDULE_ALLOW_FILE_TRANSFER_not_enabled")

    for action in normalized_actions:
        decision = store.can_run(action, policy, now=now)
        if not decision.ok:
            problems.extend(decision.problems)

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
    return (safe or f"synaps-schedule-{uuid4()}")[:120]
