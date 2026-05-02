"""Bounded read-only Codex runner window.

The window is not a daemon. It runs at most one queued Codex request through the
existing daemon runner path, with promote/enqueue disabled and sandbox locked to
read-only. It does not touch memory, passport, vector, chroma, or RAG stores.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .codex_daemon import (
    CODEX_DAEMON_RUNNER_CONFIRM_PHRASE,
    DEFAULT_CODEX_DAEMON_ROOT,
    CodexDaemon,
    CodexDaemonPolicy,
    codex_daemon_arm_status,
)
from .codex_request import DEFAULT_CODEX_REQUEST_ROOT
from .mailbox import DEFAULT_CODEX_INBOX_ROOT, DEFAULT_CODEX_RECEIPT_LEDGER
from .file_transfer import DEFAULT_QUARANTINE_ROOT
from .protocol import SynapsValidationError


CODEX_RUNNER_WINDOW_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_RUNNER_READONLY_WINDOW"
CODEX_RUNNER_WINDOW_EVENT_SCHEMA = "ester.synaps.codex_runner_window_event.v1"
DEFAULT_CODEX_RUNNER_WINDOW_ROOT = Path("data") / "synaps" / "codex_bridge" / "runner_windows"


class CodexRunnerWindowStore:
    """Append-only ledger for explicit local runner windows."""

    def __init__(self, root: str | Path = DEFAULT_CODEX_RUNNER_WINDOW_ROOT) -> None:
        root_path = Path(root)
        if not str(root_path).strip():
            raise SynapsValidationError("codex runner window root is required")
        self.root = root_path
        self.index_path = self.root / "events.jsonl"

    def record_event(self, window_id: str, event: str, summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
        safe_id = _safe_identifier(window_id)
        record = {
            "schema": CODEX_RUNNER_WINDOW_EVENT_SCHEMA,
            "event": event,
            "window_id": safe_id,
            "created_at": _iso_now(),
            "auto_ingest": False,
            "memory": "off",
            "summary": dict(summary or {}),
        }
        self._append_jsonl(self.index_path, record)
        self._append_jsonl(self.root / safe_id / "events.jsonl", record)
        return record

    def _append_jsonl(self, path: Path, record: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


def codex_runner_window_arm_status(env: Mapping[str, str]) -> dict[str, bool]:
    daemon_status = codex_daemon_arm_status(env)
    return {
        "window": _env_bool(env.get("SYNAPS_CODEX_RUNNER_WINDOW", "0")),
        "armed": _env_bool(env.get("SYNAPS_CODEX_RUNNER_WINDOW_ARMED", "0")),
        "kill_switch": _env_bool(env.get("SYNAPS_CODEX_RUNNER_WINDOW_KILL_SWITCH", "0"))
        or daemon_status["kill_switch"],
        "legacy_autochat": daemon_status["legacy_autochat"],
        "persistent": daemon_status["persistent"],
        "persistent_armed": daemon_status["persistent_armed"],
        "promote_mailbox": daemon_status["promote_mailbox"],
        "enqueue_handoffs": daemon_status["enqueue_handoffs"],
        "worker_available": daemon_status["worker_available"],
        "scheduler": _env_bool(env.get("SISTER_SCHEDULE", "0")),
        "conversation_window": _env_bool(env.get("SISTER_CONVERSATION_WINDOW", "0")),
        "file_transfer": _env_bool(env.get("SISTER_FILE_TRANSFER", "0")),
    }


def validate_codex_runner_window_gate(
    env: Mapping[str, str],
    confirm: str,
    policy: CodexDaemonPolicy,
) -> list[str]:
    status = codex_runner_window_arm_status(env)
    problems: list[str] = []
    if confirm != CODEX_RUNNER_WINDOW_CONFIRM_PHRASE:
        problems.append("missing_runner_window_confirm_phrase")
    if not status["window"]:
        problems.append("SYNAPS_CODEX_RUNNER_WINDOW_not_enabled")
    if not status["armed"]:
        problems.append("SYNAPS_CODEX_RUNNER_WINDOW_ARMED_not_enabled")
    if status["kill_switch"]:
        problems.append("SYNAPS_CODEX_RUNNER_WINDOW_KILL_SWITCH_enabled")
    if status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    if status["persistent"] or status["persistent_armed"]:
        problems.append("SYNAPS_CODEX_DAEMON_PERSISTENT_must_remain_disabled_for_runner_window")
    if status["promote_mailbox"] or status["enqueue_handoffs"]:
        problems.append("SYNAPS_CODEX_DAEMON_PROMOTE_ENQUEUE_must_remain_disabled_for_runner_window")
    if not status["worker_available"]:
        problems.append("SYNAPS_CODEX_WORKER_CAPABILITY_must_be_available_for_runner_window")
    if status["scheduler"] or status["conversation_window"] or status["file_transfer"]:
        problems.append("SYNAPS_live_send_flags_must_remain_disabled_for_runner_window")
    if str(policy.sandbox or "").strip().lower() != "read-only":
        problems.append("SYNAPS_CODEX_DAEMON_SANDBOX_must_be_read_only_for_runner_window")
    return problems


def run_codex_runner_window(
    *,
    env: Mapping[str, str],
    apply: bool = False,
    confirm: str = "",
    operator: str = "codex-runner-window",
    window_id: str | None = None,
    window_root: str | Path = DEFAULT_CODEX_RUNNER_WINDOW_ROOT,
    daemon_root: str | Path = DEFAULT_CODEX_DAEMON_ROOT,
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    inbox_root: str | Path = DEFAULT_CODEX_INBOX_ROOT,
    receipt_ledger: str | Path = DEFAULT_CODEX_RECEIPT_LEDGER,
    request_root: str | Path = DEFAULT_CODEX_REQUEST_ROOT,
    policy: CodexDaemonPolicy | None = None,
) -> dict[str, Any]:
    resolved_policy = policy or CodexDaemonPolicy.from_env(env)
    safe_window_id = _safe_identifier(window_id or f"synaps-codex-runner-window-{uuid4()}")
    store = CodexRunnerWindowStore(window_root)
    output: dict[str, Any] = {
        "ok": True,
        "dry_run": not apply,
        "window_id": safe_window_id,
        "confirm_required": CODEX_RUNNER_WINDOW_CONFIRM_PHRASE,
        "runner_confirm_required": CODEX_DAEMON_RUNNER_CONFIRM_PHRASE,
        "arm_status": codex_runner_window_arm_status(env),
        "policy": {**resolved_policy.to_record(), "max_requests_per_cycle": 1, "sandbox": "read-only"},
        "actions": [],
        "auto_ingest": False,
        "memory": "off",
    }

    if apply:
        problems = validate_codex_runner_window_gate(env, confirm, resolved_policy)
        if problems:
            output["ok"] = False
            output["result"] = {"ok": False, "error": "runner_window_gate_failed", "problems": problems}
            return output
        store.record_event(safe_window_id, "opened", {"operator": operator})

    daemon_env = dict(env)
    daemon_env.update(
        {
            "SISTER_AUTOCHAT": "0",
            "SYNAPS_CODEX_DAEMON": "1",
            "SYNAPS_CODEX_DAEMON_ARMED": "1",
            "SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX": "0",
            "SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS": "0",
            "SYNAPS_CODEX_DAEMON_RUNNER": "1",
            "SYNAPS_CODEX_DAEMON_RUNNER_ARMED": "1",
            "SYNAPS_CODEX_DAEMON_PERSISTENT": "0",
            "SYNAPS_CODEX_DAEMON_PERSISTENT_ARMED": "0",
        }
    )
    daemon_policy = replace(resolved_policy, max_requests_per_cycle=1, sandbox="read-only")
    daemon = CodexDaemon(
        daemon_root=daemon_root,
        quarantine_root=quarantine_root,
        inbox_root=inbox_root,
        receipt_ledger=receipt_ledger,
        request_root=request_root,
        policy=daemon_policy,
    )
    cycle = daemon.cycle(
        env=daemon_env,
        apply=apply,
        confirm=CODEX_DAEMON_RUNNER_CONFIRM_PHRASE,
        operator=operator,
    )
    output["ok"] = bool(cycle.get("ok"))
    output["actions"] = list(cycle.get("actions") or [])
    output["cycle"] = cycle

    if apply:
        store.record_event(
            safe_window_id,
            "closed",
            {
                "operator": operator,
                "ok": output["ok"],
                "action_count": len(output["actions"]),
            },
        )
    return output


def _env_bool(raw: str) -> bool:
    return str(raw or "0").strip().lower() in {"1", "true", "yes", "on", "y", "enabled"}


def _safe_identifier(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(raw or "").strip())
    safe = safe.strip("-_")
    if not safe:
        raise SynapsValidationError("identifier is required")
    return safe[:120]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
