"""Bounded SYNAPS conversation window contracts.

This module is deliberately small and side-effect free on import. It provides
the policy, metadata, and ledger pieces needed to run sister conversations as
operator-bounded windows rather than as an always-on loop.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .protocol import (
    SynapsConfig,
    SynapsMessageType,
    SynapsPreparedRequest,
    SynapsValidationError,
    build_envelope,
    prepare_outbound_request,
)


CONVERSATION_WINDOW_CONFIRM_PHRASE = "ESTER_READY_FOR_CONVERSATION_WINDOW"
CONVERSATION_WINDOW_MODE = "synaps_conversation_window"
DEFAULT_WINDOW_TOPIC = (
    "Bounded sister conversation window. Exchange concise operational status, "
    "one risk, and one useful next check. Do not include private data."
)


@dataclass(frozen=True)
class ConversationWindowPolicy:
    max_duration_sec: int = 15 * 60
    max_messages: int = 10
    cooldown_sec: int = 60 * 60
    max_content_chars: int = 1200
    reply_preview_chars: int = 500

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ConversationWindowPolicy":
        source = os.environ if env is None else env
        return cls(
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
            cooldown_sec=_bounded_int(
                source.get("SISTER_CONVERSATION_WINDOW_COOLDOWN_SEC"),
                default=60 * 60,
                minimum=60 * 60,
                maximum=24 * 60 * 60,
            ),
            max_content_chars=_bounded_int(
                source.get("SISTER_CONVERSATION_WINDOW_MAX_CONTENT_CHARS"),
                default=1200,
                minimum=160,
                maximum=2400,
            ),
            reply_preview_chars=_bounded_int(
                source.get("SISTER_CONVERSATION_WINDOW_REPLY_PREVIEW_CHARS"),
                default=500,
                minimum=80,
                maximum=1200,
            ),
        )

    def to_record(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class ConversationWindowGate:
    ok: bool
    problems: tuple[str, ...] = ()
    next_open_at: str = ""
    last_window_id: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "problems": list(self.problems),
            "next_open_at": self.next_open_at,
            "last_window_id": self.last_window_id,
        }


class ConversationWindowStore:
    """Append-only ledger for bounded conversation windows.

    The store is intentionally explicit-root: callers choose where operational
    transcripts live. It does not import or mutate memory/vector/passport stores.
    """

    def __init__(self, root: str | Path) -> None:
        root_path = Path(root)
        if not str(root_path).strip():
            raise SynapsValidationError("conversation window ledger root is required")
        self.root = root_path
        self.index_path = self.root / "windows.jsonl"

    def can_open(self, policy: ConversationWindowPolicy, now: datetime | None = None) -> ConversationWindowGate:
        current = _coerce_utc(now)
        latest = self._latest_open_record()
        if not latest:
            return ConversationWindowGate(ok=True)

        opened_at = _parse_utc(str(latest.get("opened_at", "")))
        if opened_at is None:
            return ConversationWindowGate(ok=True)

        next_open = opened_at + timedelta(seconds=policy.cooldown_sec)
        if current < next_open:
            return ConversationWindowGate(
                ok=False,
                problems=("conversation_window_cooldown_active",),
                next_open_at=_iso(next_open),
                last_window_id=str(latest.get("window_id", "")),
            )
        return ConversationWindowGate(ok=True)

    def open_window(
        self,
        policy: ConversationWindowPolicy,
        topic: str,
        now: datetime | None = None,
        window_id: str | None = None,
    ) -> dict[str, Any]:
        current = _coerce_utc(now)
        gate = self.can_open(policy, current)
        if not gate.ok:
            raise SynapsValidationError(",".join(gate.problems))

        actual_window_id = window_id or f"synaps-window-{uuid4()}"
        record = {
            "event": "opened",
            "window_id": actual_window_id,
            "opened_at": _iso(current),
            "deadline_at": _iso(current + timedelta(seconds=policy.max_duration_sec)),
            "policy": policy.to_record(),
            "topic_hash": _hash_text(topic),
            "topic_preview": _preview(topic, policy.reply_preview_chars),
        }
        self._append_index(record)
        self.append_event(actual_window_id, record)
        return record

    def append_event(self, window_id: str, event: Mapping[str, Any]) -> dict[str, Any]:
        event_record = dict(event)
        event_record.setdefault("window_id", window_id)
        event_record.setdefault("created_at", _iso(_utc_now()))
        self._append_jsonl(self._window_events_path(window_id), event_record)
        return event_record

    def record_turn(
        self,
        window_id: str,
        *,
        direction: str,
        message_index: int,
        content: str,
        status: str,
        policy: ConversationWindowPolicy,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "event": "turn",
            "direction": direction,
            "message_index": int(message_index),
            "content_hash": _hash_text(content),
            "content_preview": _preview(content, policy.reply_preview_chars),
            "status": status,
        }
        if extra:
            event["extra"] = dict(extra)
        return self.append_event(window_id, event)

    def close_window(
        self,
        window_id: str,
        reason: str,
        policy: ConversationWindowPolicy,
        message_count: int = 0,
    ) -> dict[str, Any]:
        return self.append_event(
            window_id,
            {
                "event": "closed",
                "reason": reason,
                "message_count": int(message_count),
                "policy": policy.to_record(),
            },
        )

    def _latest_open_record(self) -> dict[str, Any] | None:
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
            if isinstance(record, dict) and record.get("event") == "opened":
                latest = record
        return latest

    def _append_index(self, record: Mapping[str, Any]) -> None:
        self._append_jsonl(self.index_path, record)

    def _append_jsonl(self, path: Path, record: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")

    def _window_events_path(self, window_id: str) -> Path:
        safe_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in window_id)
        return self.root / safe_id / "events.jsonl"


def build_conversation_metadata(
    policy: ConversationWindowPolicy,
    *,
    window_id: str,
    message_index: int = 1,
    message_cost: int = 2,
) -> dict[str, Any]:
    return {
        "autochat_window": "bounded",
        "conversation_window": "hourly",
        "files": "manifest_only",
        "max_duration_sec": policy.max_duration_sec,
        "max_messages": policy.max_messages,
        "memory": "off",
        "message_cost": int(message_cost),
        "message_index": int(message_index),
        "mode": CONVERSATION_WINDOW_MODE,
        "operator_window": True,
        "window_id": window_id,
    }


def build_conversation_turn_request(
    config: SynapsConfig,
    policy: ConversationWindowPolicy,
    *,
    window_id: str,
    content: str = DEFAULT_WINDOW_TOPIC,
    message_index: int = 1,
) -> SynapsPreparedRequest:
    bounded_content = _preview(content, policy.max_content_chars)
    envelope = build_envelope(
        config,
        bounded_content,
        SynapsMessageType.THOUGHT_REQUEST,
        metadata=build_conversation_metadata(
            policy,
            window_id=window_id,
            message_index=message_index,
        ),
    )
    return prepare_outbound_request(config, envelope, timeout_sec=config.opinion_timeout_sec)


def conversation_window_arm_status(env: Mapping[str, str]) -> dict[str, bool]:
    return {
        "window": _env_bool(env.get("SISTER_CONVERSATION_WINDOW", "0")),
        "armed": _env_bool(env.get("SISTER_CONVERSATION_WINDOW_ARMED", "0")),
        "legacy_autochat": _env_bool(env.get("SISTER_AUTOCHAT", "0")),
    }


def validate_conversation_send_gate(
    env: Mapping[str, str],
    confirm: str,
    store: ConversationWindowStore,
    policy: ConversationWindowPolicy,
    now: datetime | None = None,
) -> list[str]:
    problems: list[str] = []
    status = conversation_window_arm_status(env)
    if confirm != CONVERSATION_WINDOW_CONFIRM_PHRASE:
        problems.append("missing_confirm_phrase")
    if not status["window"]:
        problems.append("SISTER_CONVERSATION_WINDOW_not_enabled")
    if not status["armed"]:
        problems.append("SISTER_CONVERSATION_WINDOW_ARMED_not_enabled")
    if status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    gate = store.can_open(policy, now=now)
    if not gate.ok:
        problems.extend(gate.problems)
    return problems


def _bounded_int(raw: str | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(raw if raw is not None else default).strip())
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _env_bool(raw: str) -> bool:
    return str(raw or "0").strip().lower() in {"1", "true", "yes", "on", "y"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime | None) -> datetime:
    if value is None:
        return _utc_now()
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


def _hash_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _preview(text: str, limit: int) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)] + "..."
