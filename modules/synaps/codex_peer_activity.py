"""Bounded peer activity detector for SYNAPS Codex handoffs.

This layer classifies a peer package as report-ready, status-ready, silent, or
ambiguous. It never promotes to inbox, enqueues requests, executes Codex, or
starts a persistent loop.
"""

from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .codex_daemon import (
    DEFAULT_CODEX_DAEMON_ROOT,
    DEFAULT_CODEX_INBOX_ROOT,
    DEFAULT_CODEX_RECEIPT_LEDGER,
    DEFAULT_CODEX_REQUEST_ROOT,
    CodexDaemonPolicy,
)
from .codex_report_observer import (
    CODEX_REPORT_SELECTOR_CONFIRM_PHRASE,
    CODEX_REPORT_SELECTOR_SCHEMA,
    CodexReportSelector,
    select_codex_report_by_manifest,
    validate_codex_report_observer_gate,
)
from .file_transfer import DEFAULT_QUARANTINE_ROOT


CODEX_PEER_ACTIVITY_SCHEMA = "ester.synaps.codex_peer_activity.v1"
CODEX_PEER_ACTIVITY_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_PEER_ACTIVITY_APPLY"


@dataclass(frozen=True)
class CodexPeerActivityPolicy:
    max_cycles: int = 3
    sleep_sec: float = 5.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexPeerActivityPolicy":
        source = os.environ if env is None else env
        return cls(
            max_cycles=_bounded_int(source.get("SYNAPS_CODEX_PEER_ACTIVITY_MAX_CYCLES"), 3, 1, 120),
            sleep_sec=_bounded_float(source.get("SYNAPS_CODEX_PEER_ACTIVITY_SLEEP_SEC"), 5.0, 0.0, 300.0),
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodexPeerActivitySelectors:
    expected_report: CodexReportSelector
    status_report: CodexReportSelector | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "expected_report": self.expected_report.to_record(),
            "status_report": self.status_report.to_record() if self.status_report else None,
        }


def validate_codex_peer_activity_gate(env: Mapping[str, str], *, apply: bool = False, confirm: str = "") -> list[str]:
    problems = validate_codex_report_observer_gate(env, apply=False)
    if apply and confirm != CODEX_PEER_ACTIVITY_CONFIRM_PHRASE:
        problems.append("missing_codex_peer_activity_confirm_phrase")
    return problems


def watch_codex_peer_activity(
    *,
    selectors: CodexPeerActivitySelectors,
    env: Mapping[str, str] | None = None,
    apply: bool = False,
    confirm: str = "",
    operator: str = "codex-peer-activity",
    daemon_root: str | Path = DEFAULT_CODEX_DAEMON_ROOT,
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    inbox_root: str | Path = DEFAULT_CODEX_INBOX_ROOT,
    receipt_ledger: str | Path = DEFAULT_CODEX_RECEIPT_LEDGER,
    request_root: str | Path = DEFAULT_CODEX_REQUEST_ROOT,
    daemon_policy: CodexDaemonPolicy | None = None,
    policy: CodexPeerActivityPolicy | None = None,
    sleep_fn=time.sleep,
) -> dict[str, Any]:
    actual_env = os.environ if env is None else env
    actual_policy = policy or CodexPeerActivityPolicy.from_env(actual_env)
    gate_problems = validate_codex_peer_activity_gate(actual_env, apply=apply, confirm=confirm)
    output: dict[str, Any] = {
        "schema": CODEX_PEER_ACTIVITY_SCHEMA,
        "ok": not gate_problems,
        "dry_run": not apply,
        "confirm_required": CODEX_PEER_ACTIVITY_CONFIRM_PHRASE,
        "selectors": selectors.to_record(),
        "policy": actual_policy.to_record(),
        "cycles": [],
        "problems": list(gate_problems),
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
    }
    if gate_problems:
        output["result"] = {"ok": False, "status": "gate_failed", "problems": gate_problems}
        return _finish(output)

    for index in range(actual_policy.max_cycles):
        expected = _select_branch(
            selectors.expected_report,
            env=actual_env,
            operator=operator,
            daemon_root=daemon_root,
            quarantine_root=quarantine_root,
            inbox_root=inbox_root,
            receipt_ledger=receipt_ledger,
            request_root=request_root,
            daemon_policy=daemon_policy,
        )
        status = (
            _select_branch(
                selectors.status_report,
                env=actual_env,
                operator=operator,
                daemon_root=daemon_root,
                quarantine_root=quarantine_root,
                inbox_root=inbox_root,
                receipt_ledger=receipt_ledger,
                request_root=request_root,
                daemon_policy=daemon_policy,
            )
            if selectors.status_report
            else {"enabled": False, "candidate_count": 0, "matched": False, "candidates": [], "problems": []}
        )
        cycle = {
            "cycle": index + 1,
            "expected_report": expected,
            "status_report": status,
        }
        output["cycles"].append(cycle)

        branch_problems = [*_branch_count_problems("expected_report", expected), *_branch_count_problems("status_report", status)]
        if branch_problems:
            output["ok"] = False
            output["problems"].extend(branch_problems)
            output["result"] = {"ok": False, "status": "peer_activity_ambiguous", "problems": branch_problems}
            return _finish(output)

        matches = []
        if expected.get("matched"):
            matches.append(("expected_report", expected))
        if status.get("matched"):
            matches.append(("status_report", status))
        if len(matches) > 1:
            output["ok"] = False
            output["matched"] = False
            output["problems"].append("multiple_peer_activity_branches_matched")
            output["result"] = {"ok": False, "status": "peer_activity_ambiguous", "problems": ["multiple_peer_activity_branches_matched"]}
            return _finish(output)
        if len(matches) == 1:
            branch, selected = matches[0]
            output["matched"] = True
            output["branch"] = branch
            output["selected_transfer_id"] = selected.get("selected_transfer_id", "")
            if not apply:
                output["result"] = {
                    "ok": True,
                    "status": "expected_report_ready" if branch == "expected_report" else "peer_status_ready",
                }
                return _finish(output)
            applied = _apply_branch(
                selectors.expected_report if branch == "expected_report" else selectors.status_report,
                env=actual_env,
                operator=operator,
                daemon_root=daemon_root,
                quarantine_root=quarantine_root,
                inbox_root=inbox_root,
                receipt_ledger=receipt_ledger,
                request_root=request_root,
                daemon_policy=daemon_policy,
            )
            cycle["apply"] = _compact_selector_payload(applied)
            output["ok"] = bool(applied.get("ok"))
            output["result"] = {
                "ok": output["ok"],
                "status": _observed_status(branch) if output["ok"] else str((applied.get("result") or {}).get("status") or "apply_failed"),
                "problems": list(applied.get("problems") or []),
            }
            output["problems"].extend(list(applied.get("problems") or []))
            return _finish(output)

        if index + 1 < actual_policy.max_cycles and actual_policy.sleep_sec:
            sleep_fn(actual_policy.sleep_sec)

    output["matched"] = False
    output["result"] = {"ok": True, "status": "peer_silent", "cycles": actual_policy.max_cycles}
    output["ok"] = True
    return _finish(output)


def _select_branch(
    selector: CodexReportSelector | None,
    *,
    env: Mapping[str, str],
    operator: str,
    daemon_root: str | Path,
    quarantine_root: str | Path,
    inbox_root: str | Path,
    receipt_ledger: str | Path,
    request_root: str | Path,
    daemon_policy: CodexDaemonPolicy | None,
) -> dict[str, Any]:
    if selector is None:
        return {"enabled": False, "candidate_count": 0, "matched": False, "candidates": [], "problems": []}
    payload = select_codex_report_by_manifest(
        selector=selector,
        env=env,
        apply=False,
        operator=operator,
        daemon_root=daemon_root,
        quarantine_root=quarantine_root,
        inbox_root=inbox_root,
        receipt_ledger=receipt_ledger,
        request_root=request_root,
        policy=daemon_policy,
    )
    compact = _compact_selector_payload(payload)
    compact["enabled"] = True
    return compact


def _apply_branch(
    selector: CodexReportSelector | None,
    *,
    env: Mapping[str, str],
    operator: str,
    daemon_root: str | Path,
    quarantine_root: str | Path,
    inbox_root: str | Path,
    receipt_ledger: str | Path,
    request_root: str | Path,
    daemon_policy: CodexDaemonPolicy | None,
) -> dict[str, Any]:
    if selector is None:
        return {"ok": False, "result": {"status": "missing_selector"}, "problems": ["missing_selector"]}
    return select_codex_report_by_manifest(
        selector=selector,
        env=env,
        apply=True,
        confirm=CODEX_REPORT_SELECTOR_CONFIRM_PHRASE,
        operator=operator,
        daemon_root=daemon_root,
        quarantine_root=quarantine_root,
        inbox_root=inbox_root,
        receipt_ledger=receipt_ledger,
        request_root=request_root,
        policy=daemon_policy,
    )


def _compact_selector_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    candidates = list(payload.get("candidates") or [])
    return {
        "schema": payload.get("schema", CODEX_REPORT_SELECTOR_SCHEMA),
        "ok": bool(payload.get("ok")),
        "matched": bool(payload.get("matched")),
        "selected_transfer_id": str(payload.get("selected_transfer_id") or ""),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "problems": list(payload.get("problems") or []),
        "result": dict(payload.get("result") or {}),
        "auto_ingest": False,
        "memory": "off",
    }


def _branch_count_problems(branch: str, payload: Mapping[str, Any]) -> list[str]:
    count = int(payload.get("candidate_count") or 0)
    if count > 1:
        return [f"{branch}:expected_at_most_one_manifest_report:{count}"]
    return []


def _finish(payload: dict[str, Any]) -> dict[str, Any]:
    payload["cycle_count"] = len(payload.get("cycles") or [])
    return payload


def _observed_status(branch: str) -> str:
    return "expected_report_observed" if branch == "expected_report" else "peer_status_observed"


def _bounded_int(raw: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _bounded_float(raw: str | None, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(raw) if raw is not None else default
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))
