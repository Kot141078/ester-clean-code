"""Expected-transfer observer for SYNAPS Codex reports.

This wrapper turns the daemon report observer into an exact-match operation:
apply is allowed only when dry-run finds exactly the requested report transfer.
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from .codex_daemon import (
    CODEX_DAEMON_CONFIRM_PHRASE,
    DEFAULT_CODEX_DAEMON_ROOT,
    CodexDaemon,
    CodexDaemonPolicy,
    codex_daemon_arm_status,
)
from .mailbox import DEFAULT_CODEX_INBOX_ROOT, DEFAULT_CODEX_RECEIPT_LEDGER
from .codex_request import DEFAULT_CODEX_REQUEST_ROOT
from .file_transfer import DEFAULT_QUARANTINE_ROOT
from .protocol import SynapsValidationError


CODEX_REPORT_OBSERVER_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_REPORT_OBSERVER_APPLY"
CODEX_REPORT_OBSERVER_SCHEMA = "ester.synaps.codex_report_observer.v1"


def validate_codex_report_observer_gate(
    env: Mapping[str, str],
    *,
    apply: bool = False,
    confirm: str = "",
) -> list[str]:
    status = codex_daemon_arm_status(env)
    problems: list[str] = []
    if not status["daemon"]:
        problems.append("SYNAPS_CODEX_DAEMON_not_enabled")
    if not status["armed"]:
        problems.append("SYNAPS_CODEX_DAEMON_ARMED_not_enabled")
    if not status["observe_reports"]:
        problems.append("SYNAPS_CODEX_DAEMON_OBSERVE_REPORTS_not_enabled")
    if not status["observe_reports_armed"]:
        problems.append("SYNAPS_CODEX_DAEMON_OBSERVE_REPORTS_ARMED_not_enabled")
    if status["promote_mailbox"]:
        problems.append("SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX_must_remain_disabled")
    if status["enqueue_handoffs"]:
        problems.append("SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS_must_remain_disabled")
    if status["runner"] or status["runner_armed"]:
        problems.append("SYNAPS_CODEX_DAEMON_RUNNER_must_remain_disabled")
    if status["persistent"] or status["persistent_armed"]:
        problems.append("SYNAPS_CODEX_DAEMON_PERSISTENT_must_remain_disabled")
    if status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    if status["kill_switch"]:
        problems.append("SYNAPS_CODEX_DAEMON_KILL_SWITCH_enabled")
    if apply and confirm != CODEX_REPORT_OBSERVER_CONFIRM_PHRASE:
        problems.append("missing_codex_report_observer_confirm_phrase")
    return problems


def observe_expected_codex_report(
    *,
    expected_transfer_id: str,
    env: Mapping[str, str] | None = None,
    apply: bool = False,
    confirm: str = "",
    operator: str = "codex-report-observer",
    daemon_root: str | Path = DEFAULT_CODEX_DAEMON_ROOT,
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    inbox_root: str | Path = DEFAULT_CODEX_INBOX_ROOT,
    receipt_ledger: str | Path = DEFAULT_CODEX_RECEIPT_LEDGER,
    request_root: str | Path = DEFAULT_CODEX_REQUEST_ROOT,
    policy: CodexDaemonPolicy | None = None,
) -> dict[str, Any]:
    safe_transfer_id = _safe_transfer_id(expected_transfer_id)
    actual_env = os.environ if env is None else env
    actual_policy = replace(policy or CodexDaemonPolicy.from_env(actual_env), max_reports_per_cycle=1)
    daemon = CodexDaemon(
        daemon_root=daemon_root,
        quarantine_root=quarantine_root,
        inbox_root=inbox_root,
        receipt_ledger=receipt_ledger,
        request_root=request_root,
        policy=actual_policy,
    )
    status = codex_daemon_arm_status(actual_env)
    gate_problems = validate_codex_report_observer_gate(actual_env, apply=apply, confirm=confirm)
    preview = daemon.cycle(env=actual_env, apply=False, operator=operator)
    match_problems = _expected_action_problems(preview.get("actions") or [], safe_transfer_id)
    matched = not match_problems
    payload: dict[str, Any] = {
        "schema": CODEX_REPORT_OBSERVER_SCHEMA,
        "ok": not gate_problems if not apply else not gate_problems and matched,
        "dry_run": not apply,
        "confirm_required": CODEX_REPORT_OBSERVER_CONFIRM_PHRASE,
        "expected_transfer_id": safe_transfer_id,
        "matched": matched,
        "arm_status": status,
        "policy": actual_policy.to_record(),
        "preview": _compact_cycle(preview),
        "problems": [*gate_problems, *match_problems],
        "auto_ingest": False,
        "memory": "off",
    }
    if not apply:
        return payload
    if gate_problems:
        payload["result"] = {"ok": False, "status": "gate_failed", "problems": gate_problems}
        return payload
    if match_problems:
        payload["result"] = {"ok": False, "status": "expected_transfer_mismatch", "problems": match_problems}
        return payload

    result = daemon.cycle(env=actual_env, apply=True, confirm=CODEX_DAEMON_CONFIRM_PHRASE, operator=operator)
    apply_problems = _expected_action_problems(result.get("actions") or [], safe_transfer_id)
    payload["apply"] = _compact_cycle(result)
    payload["ok"] = bool(result.get("ok")) and not apply_problems
    payload["problems"].extend(apply_problems)
    payload["result"] = {
        "ok": payload["ok"],
        "status": "report_observed" if payload["ok"] else "apply_result_mismatch",
        "problems": apply_problems,
    }
    return payload


def _expected_action_problems(actions: list[Mapping[str, Any]], expected_transfer_id: str) -> list[str]:
    if len(actions) != 1:
        return [f"expected_exactly_one_observe_report_action:{len(actions)}"]
    action = actions[0]
    if action.get("action") != "observe_report":
        return [f"unexpected_action:{action.get('action')}"]
    if str(action.get("transfer_id") or "") != expected_transfer_id:
        return [f"unexpected_transfer_id:{action.get('transfer_id')}"]
    if action.get("auto_ingest") is not False or action.get("memory") != "off":
        return ["unsafe_observe_report_action"]
    return []


def _compact_cycle(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(payload.get("ok")),
        "dry_run": bool(payload.get("dry_run")),
        "actions": list(payload.get("actions") or []),
        "auto_ingest": False,
        "memory": "off",
    }


def _safe_transfer_id(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(raw or "").strip()).strip("-_")
    if not safe:
        raise SynapsValidationError("expected transfer id is required")
    return safe[:120]
