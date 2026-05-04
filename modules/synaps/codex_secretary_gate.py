"""Bounded Secretary-Codex next-work response gate.

The gate waits for exactly one of two quarantined responses:
an actionable next-work contract or an idle report. It only reads SYNAPS
quarantine metadata and can optionally mark the selected transfer as seen.
"""

from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .codex_coordination_scanner import (
    CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE,
    CODEX_COORDINATION_SCANNER_MARK_CONFIRM_PHRASE,
    DEFAULT_CODEX_COORDINATION_SCANNER_ROOT,
    CodexCoordinationScannerPolicy,
    CodexCoordinationSelector,
    scan_codex_coordination_message,
)
from .codex_daemon import codex_daemon_arm_status
from .file_transfer import DEFAULT_QUARANTINE_ROOT
from .mailbox import DEFAULT_CODEX_INBOX_ROOT


CODEX_SECRETARY_GATE_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_SECRETARY_GATE_RUN"
CODEX_SECRETARY_GATE_SCHEMA = "ester.synaps.codex_secretary_gate.v1"
DEFAULT_CODEX_SECRETARY_GATE_ROOT = Path("data") / "synaps" / "codex_bridge" / "secretary_gate"


@dataclass(frozen=True)
class CodexSecretaryResponsePolicy:
    max_cycles: int = 3
    sleep_sec: float = 5.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexSecretaryResponsePolicy":
        source = os.environ if env is None else env
        return cls(
            max_cycles=_bounded_int(source.get("SYNAPS_CODEX_SECRETARY_GATE_MAX_CYCLES"), 3, 1, 240),
            sleep_sec=_bounded_float(source.get("SYNAPS_CODEX_SECRETARY_GATE_SLEEP_SEC"), 5.0, 0.0, 300.0),
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodexSecretaryResponseSelectors:
    next_work: CodexCoordinationSelector
    idle: CodexCoordinationSelector

    def to_record(self) -> dict[str, Any]:
        return {
            "next_work": self.next_work.to_record(),
            "idle": self.idle.to_record(),
        }


def validate_codex_secretary_gate(
    env: Mapping[str, str],
    *,
    confirm: str = "",
) -> list[str]:
    status = codex_daemon_arm_status(env)
    problems: list[str] = []
    if confirm != CODEX_SECRETARY_GATE_CONFIRM_PHRASE:
        problems.append("missing_codex_secretary_gate_confirm_phrase")
    if not _env_bool(env.get("SYNAPS_CODEX_SECRETARY_GATE", "0")):
        problems.append("SYNAPS_CODEX_SECRETARY_GATE_not_enabled")
    if not _env_bool(env.get("SYNAPS_CODEX_SECRETARY_GATE_ARMED", "0")):
        problems.append("SYNAPS_CODEX_SECRETARY_GATE_ARMED_not_enabled")
    if status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    if status["persistent"] or status["persistent_armed"]:
        problems.append("SYNAPS_CODEX_DAEMON_PERSISTENT_must_remain_disabled")
    if status["runner"] or status["runner_armed"]:
        problems.append("SYNAPS_CODEX_DAEMON_RUNNER_must_remain_disabled")
    if status["promote_mailbox"]:
        problems.append("SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX_must_remain_disabled")
    if status["enqueue_handoffs"]:
        problems.append("SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS_must_remain_disabled")
    if status["kill_switch"]:
        problems.append("SYNAPS_CODEX_DAEMON_KILL_SWITCH_enabled")
    return problems


def run_codex_secretary_response_gate(
    *,
    selectors: CodexSecretaryResponseSelectors,
    env: Mapping[str, str] | None = None,
    apply: bool = False,
    confirm: str = "",
    operator: str = "codex-secretary-gate",
    secretary_root: str | Path = DEFAULT_CODEX_SECRETARY_GATE_ROOT,
    scanner_root: str | Path = DEFAULT_CODEX_COORDINATION_SCANNER_ROOT,
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    inbox_root: str | Path = DEFAULT_CODEX_INBOX_ROOT,
    policy: CodexSecretaryResponsePolicy | None = None,
    sleep_fn=time.sleep,
) -> dict[str, Any]:
    actual_env = os.environ if env is None else env
    actual_policy = policy or CodexSecretaryResponsePolicy.from_env(actual_env)
    gate_problems = validate_codex_secretary_gate(actual_env, confirm=confirm)
    output: dict[str, Any] = {
        "schema": CODEX_SECRETARY_GATE_SCHEMA,
        "ok": not gate_problems,
        "dry_run": not apply,
        "apply": apply,
        "confirm_required": CODEX_SECRETARY_GATE_CONFIRM_PHRASE,
        "selector": selectors.to_record(),
        "policy": actual_policy.to_record(),
        "cycles": [],
        "problems": list(gate_problems),
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
        "secretary_root": str(Path(secretary_root)),
    }
    if gate_problems:
        output["result"] = {"ok": False, "status": "gate_failed", "problems": gate_problems}
        return _finish(output)

    scanner_env = _scanner_env(actual_env)
    for index in range(actual_policy.max_cycles):
        cycle: dict[str, Any] = {"cycle": index + 1}
        next_payload = _scan_once(
            selectors.next_work,
            env=scanner_env,
            mark_seen=False,
            operator=f"{operator}-next-work",
            scanner_root=scanner_root,
            quarantine_root=quarantine_root,
            inbox_root=inbox_root,
        )
        idle_payload = _scan_once(
            selectors.idle,
            env=scanner_env,
            mark_seen=False,
            operator=f"{operator}-idle",
            scanner_root=scanner_root,
            quarantine_root=quarantine_root,
            inbox_root=inbox_root,
        )
        cycle["next_work"] = _compact_scan(next_payload)
        cycle["idle"] = _compact_scan(idle_payload)
        output["cycles"].append(cycle)

        scan_problems = [
            *_unexpected_scan_problems("next_work", next_payload),
            *_unexpected_scan_problems("idle", idle_payload),
        ]
        if scan_problems:
            output["ok"] = False
            output["problems"].extend(scan_problems)
            output["result"] = {"ok": False, "status": "scanner_failed", "problems": scan_problems}
            return _finish(output)

        selected = []
        if next_payload.get("matched"):
            selected.append(("next_work", selectors.next_work, next_payload))
        if idle_payload.get("matched"):
            selected.append(("idle", selectors.idle, idle_payload))
        if len(selected) > 1:
            output["ok"] = False
            output["matched"] = False
            output["problems"].append("multiple_secretary_responses")
            output["result"] = {"ok": False, "status": "multiple_secretary_responses"}
            return _finish(output)
        if len(selected) == 1:
            branch, selector, payload = selected[0]
            selected_transfer_id = str(payload.get("selected_transfer_id") or "")
            output["matched"] = True
            output["selected_branch"] = branch
            output["selected_transfer_id"] = selected_transfer_id
            if not apply:
                output["result"] = {
                    "ok": True,
                    "status": "would_select_secretary_response",
                    "selected_branch": branch,
                }
                return _finish(output)
            mark_payload = _scan_once(
                selector,
                env=scanner_env,
                mark_seen=True,
                operator=f"{operator}-{branch}-mark",
                scanner_root=scanner_root,
                quarantine_root=quarantine_root,
                inbox_root=inbox_root,
            )
            output["mark_seen_result"] = _compact_scan(mark_payload)
            if not mark_payload.get("ok") or not mark_payload.get("matched"):
                output["ok"] = False
                output["problems"].append("secretary_response_mark_seen_failed")
                output["result"] = {"ok": False, "status": "mark_seen_failed"}
                return _finish(output)
            repeat_payload = _scan_once(
                selector,
                env=scanner_env,
                mark_seen=False,
                operator=f"{operator}-{branch}-repeat",
                scanner_root=scanner_root,
                quarantine_root=quarantine_root,
                inbox_root=inbox_root,
            )
            output["repeat_check"] = _compact_scan(repeat_payload)
            if repeat_payload.get("matched"):
                output["ok"] = False
                output["problems"].append("secretary_response_repeat_still_matches")
                output["result"] = {"ok": False, "status": "repeat_check_failed"}
                return _finish(output)
            output["ok"] = True
            output["result"] = {
                "ok": True,
                "status": "secretary_response_seen",
                "selected_branch": branch,
            }
            return _finish(output)

        if index + 1 < actual_policy.max_cycles and actual_policy.sleep_sec:
            sleep_fn(actual_policy.sleep_sec)

    output["matched"] = False
    output["ok"] = not apply
    output["result"] = {
        "ok": not apply,
        "status": "secretary_response_not_found",
        "cycles": actual_policy.max_cycles,
    }
    return _finish(output)


def _scan_once(
    selector: CodexCoordinationSelector,
    *,
    env: Mapping[str, str],
    mark_seen: bool,
    operator: str,
    scanner_root: str | Path,
    quarantine_root: str | Path,
    inbox_root: str | Path,
) -> dict[str, Any]:
    return scan_codex_coordination_message(
        selector=selector,
        env=env,
        mark_seen=mark_seen,
        confirm=CODEX_COORDINATION_SCANNER_MARK_CONFIRM_PHRASE if mark_seen else CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE,
        operator=operator,
        scanner_root=scanner_root,
        quarantine_root=quarantine_root,
        inbox_root=inbox_root,
        policy=CodexCoordinationScannerPolicy(max_cycles=1, sleep_sec=0),
    )


def _compact_scan(payload: Mapping[str, Any]) -> dict[str, Any]:
    cycles = list(payload.get("cycles") or [])
    last_cycle = cycles[-1] if cycles else {}
    return {
        "ok": bool(payload.get("ok")),
        "matched": bool(payload.get("matched")),
        "selected_transfer_id": str(payload.get("selected_transfer_id") or ""),
        "candidate_count": int(last_cycle.get("candidate_count") or 0),
        "status": str((payload.get("result") or {}).get("status") or ""),
        "problems": list(payload.get("problems") or []),
    }


def _unexpected_scan_problems(branch: str, payload: Mapping[str, Any]) -> list[str]:
    status = str((payload.get("result") or {}).get("status") or "")
    if payload.get("ok") is True:
        return []
    if status == "not_found":
        return []
    return [f"{branch}:{problem}" for problem in list(payload.get("problems") or [status or "scanner_not_ok"])]


def _scanner_env(env: Mapping[str, str]) -> dict[str, str]:
    mapped = dict(env)
    mapped["SYNAPS_CODEX_COORDINATION_SCANNER"] = "1"
    mapped["SYNAPS_CODEX_COORDINATION_SCANNER_ARMED"] = "1"
    return mapped


def _finish(output: dict[str, Any]) -> dict[str, Any]:
    output["cycle_count"] = len(output.get("cycles") or [])
    return output


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _env_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
