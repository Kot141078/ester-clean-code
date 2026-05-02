"""Expected-transfer observer for SYNAPS Codex reports.

This wrapper turns the daemon report observer into an exact-match operation:
apply is allowed only when dry-run finds exactly the requested report transfer.
"""

from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .codex_daemon import (
    CODEX_DAEMON_CONFIRM_PHRASE,
    DEFAULT_CODEX_DAEMON_ROOT,
    CodexDaemon,
    CodexDaemonPolicy,
    codex_daemon_arm_status,
)
from .mailbox import DEFAULT_CODEX_INBOX_ROOT, DEFAULT_CODEX_RECEIPT_LEDGER, inspect_codex_mailbox_transfer
from .codex_request import DEFAULT_CODEX_REQUEST_ROOT
from .file_transfer import DEFAULT_QUARANTINE_ROOT
from .protocol import SynapsValidationError


CODEX_REPORT_OBSERVER_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_REPORT_OBSERVER_APPLY"
CODEX_REPORT_OBSERVER_SCHEMA = "ester.synaps.codex_report_observer.v1"
CODEX_REPORT_WATCHER_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_REPORT_WATCHER_RUN"
CODEX_REPORT_WATCHER_SCHEMA = "ester.synaps.codex_report_watcher.v1"
_EXACT_OBSERVER_SCAN_LIMIT = 20


@dataclass(frozen=True)
class CodexReportWatcherPolicy:
    max_cycles: int = 3
    sleep_sec: float = 5.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexReportWatcherPolicy":
        source = os.environ if env is None else env
        return cls(
            max_cycles=_bounded_int(source.get("SYNAPS_CODEX_REPORT_WATCHER_MAX_CYCLES"), 3, 1, 20),
            sleep_sec=_bounded_float(source.get("SYNAPS_CODEX_REPORT_WATCHER_SLEEP_SEC"), 5.0, 0.0, 300.0),
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


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
    actual_policy = replace(policy or CodexDaemonPolicy.from_env(actual_env), max_reports_per_cycle=_EXACT_OBSERVER_SCAN_LIMIT)
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

    fresh_preview = daemon.cycle(env=actual_env, apply=False, operator=operator)
    fresh_problems = _expected_action_problems(fresh_preview.get("actions") or [], safe_transfer_id)
    payload["pre_apply"] = _compact_cycle(fresh_preview)
    if fresh_problems:
        payload["ok"] = False
        payload["problems"].extend(fresh_problems)
        payload["result"] = {"ok": False, "status": "pre_apply_mismatch", "problems": fresh_problems}
        return payload

    result = _apply_expected_report_observation(
        daemon=daemon,
        transfer_id=safe_transfer_id,
        quarantine_root=quarantine_root,
        inbox_root=inbox_root,
        operator=operator,
    )
    apply_problems = result.get("problems") or []
    payload["apply"] = _compact_exact_apply(result)
    payload["ok"] = bool(result.get("ok")) and not apply_problems
    payload["problems"].extend(apply_problems)
    payload["result"] = {
        "ok": payload["ok"],
        "status": "report_observed" if payload["ok"] else str(result.get("status") or "apply_result_mismatch"),
        "problems": apply_problems,
    }
    return payload


def watch_expected_codex_report(
    *,
    expected_transfer_id: str,
    env: Mapping[str, str] | None = None,
    apply: bool = False,
    confirm: str = "",
    operator: str = "codex-report-watcher",
    daemon_root: str | Path = DEFAULT_CODEX_DAEMON_ROOT,
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    inbox_root: str | Path = DEFAULT_CODEX_INBOX_ROOT,
    receipt_ledger: str | Path = DEFAULT_CODEX_RECEIPT_LEDGER,
    request_root: str | Path = DEFAULT_CODEX_REQUEST_ROOT,
    daemon_policy: CodexDaemonPolicy | None = None,
    watcher_policy: CodexReportWatcherPolicy | None = None,
    sleep_fn=time.sleep,
) -> dict[str, Any]:
    safe_transfer_id = _safe_transfer_id(expected_transfer_id)
    actual_env = os.environ if env is None else env
    actual_watcher_policy = watcher_policy or CodexReportWatcherPolicy.from_env(actual_env)
    gate_problems = validate_codex_report_watcher_gate(actual_env, apply=apply, confirm=confirm)
    output: dict[str, Any] = {
        "schema": CODEX_REPORT_WATCHER_SCHEMA,
        "ok": not gate_problems,
        "dry_run": not apply,
        "confirm_required": CODEX_REPORT_WATCHER_CONFIRM_PHRASE,
        "expected_transfer_id": safe_transfer_id,
        "policy": actual_watcher_policy.to_record(),
        "cycles": [],
        "problems": list(gate_problems),
        "auto_ingest": False,
        "memory": "off",
    }
    if gate_problems:
        output["result"] = {"ok": False, "status": "gate_failed", "problems": gate_problems}
        return output

    for index in range(actual_watcher_policy.max_cycles):
        preview = observe_expected_codex_report(
            expected_transfer_id=safe_transfer_id,
            env=actual_env,
            apply=False,
            operator=operator,
            daemon_root=daemon_root,
            quarantine_root=quarantine_root,
            inbox_root=inbox_root,
            receipt_ledger=receipt_ledger,
            request_root=request_root,
            policy=daemon_policy,
        )
        cycle = {
            "cycle": index + 1,
            "matched": bool(preview.get("matched")),
            "preview": preview.get("preview"),
            "problems": list(preview.get("problems") or []),
        }
        output["cycles"].append(cycle)
        if preview.get("matched"):
            output["matched"] = True
            if not apply:
                output["result"] = {"ok": True, "status": "would_observe"}
                return output
            applied = observe_expected_codex_report(
                expected_transfer_id=safe_transfer_id,
                env=actual_env,
                apply=True,
                confirm=CODEX_REPORT_OBSERVER_CONFIRM_PHRASE,
                operator=operator,
                daemon_root=daemon_root,
                quarantine_root=quarantine_root,
                inbox_root=inbox_root,
                receipt_ledger=receipt_ledger,
                request_root=request_root,
                policy=daemon_policy,
            )
            cycle["apply"] = applied.get("apply")
            output["ok"] = bool(applied.get("ok"))
            output["result"] = dict(applied.get("result") or {})
            output["problems"].extend(list(applied.get("problems") or []))
            return output
        if not apply:
            output["matched"] = False
            output["result"] = {"ok": True, "status": "not_observed_yet"}
            return output
        if index + 1 < actual_watcher_policy.max_cycles and actual_watcher_policy.sleep_sec:
            sleep_fn(actual_watcher_policy.sleep_sec)

    output["matched"] = False
    output["ok"] = False if apply else output["ok"]
    output["result"] = {
        "ok": False,
        "status": "expected_transfer_not_observed",
        "cycles": actual_watcher_policy.max_cycles,
    }
    return output


def validate_codex_report_watcher_gate(
    env: Mapping[str, str],
    *,
    apply: bool = False,
    confirm: str = "",
) -> list[str]:
    problems = validate_codex_report_observer_gate(env, apply=False)
    if apply and confirm != CODEX_REPORT_WATCHER_CONFIRM_PHRASE:
        problems.append("missing_codex_report_watcher_confirm_phrase")
    return problems


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


def _apply_expected_report_observation(
    *,
    daemon: CodexDaemon,
    transfer_id: str,
    quarantine_root: str | Path,
    inbox_root: str | Path,
    operator: str,
) -> dict[str, Any]:
    problems: list[str] = []
    inspection = inspect_codex_mailbox_transfer(transfer_id, quarantine_root, inbox_root)
    files = list(inspection.get("files") or [])
    kinds = sorted({str(item.get("kind") or "") for item in files if item.get("kind")})
    action: dict[str, Any] = {
        "action": "observe_report",
        "transfer_id": transfer_id,
        "dry_run": False,
        "file_count": len(files),
        "kinds": kinds,
        "auto_ingest": False,
        "memory": "off",
    }
    if not inspection.get("ok"):
        problems.extend(list(inspection.get("problems") or ["inspection_failed"]))
    if inspection.get("status") not in {"ready", "already_promoted"}:
        problems.append(f"unexpected_report_status:{inspection.get('status')}")
    if "codex_report" not in set(kinds):
        problems.append("expected_transfer_is_not_codex_report")
    if daemon._promote_seen_path(transfer_id).exists():
        problems.append("expected_transfer_already_observed")
    if problems:
        action["result"] = {"ok": False, "status": "exact_apply_rejected", "problems": problems}
        return {"ok": False, "status": "exact_apply_rejected", "problems": problems, "action": action}

    result = {"ok": True, "status": "report_observed", "source": "quarantine"}
    daemon._mark_promote_seen(transfer_id, operator, result)
    daemon._append_event({"event": "report_observed", "transfer_id": transfer_id, "operator": operator})
    action["result"] = result
    return {"ok": True, "status": "report_observed", "problems": [], "action": action}


def _compact_exact_apply(payload: Mapping[str, Any]) -> dict[str, Any]:
    action = payload.get("action")
    return {
        "ok": bool(payload.get("ok")),
        "dry_run": False,
        "actions": [dict(action)] if isinstance(action, Mapping) else [],
        "auto_ingest": False,
        "memory": "off",
    }


def _safe_transfer_id(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(raw or "").strip()).strip("-_")
    if not safe:
        raise SynapsValidationError("expected transfer id is required")
    return safe[:120]


def _bounded_int(raw: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(raw).strip()) if raw is not None and str(raw).strip() else default
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _bounded_float(raw: str | None, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(str(raw).strip()) if raw is not None and str(raw).strip() else default
    except Exception:
        value = default
    return max(minimum, min(maximum, value))
