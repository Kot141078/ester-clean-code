"""Bounded SYNAPS Codex coordination session wrapper.

The session runner composes already-proven one-shot cycle phases. It is not a
daemon: a finite plan is loaded, each step runs once, and the process exits.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .codex_coordination_cycle import (
    CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
    DEFAULT_CODEX_COORDINATION_CYCLE_ROOT,
    PHASE_SEND_FILE,
    PHASE_WAIT_CONTRACT,
    PHASE_WAIT_REPORT,
    CodexCoordinationCyclePolicy,
    CodexCoordinationSendSpec,
    run_codex_coordination_cycle_phase,
)
from .codex_coordination_scanner import CodexCoordinationSelector
from .codex_daemon import DEFAULT_CODEX_DAEMON_ROOT, codex_daemon_arm_status
from .codex_front_claim import (
    CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE,
    CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
    DEFAULT_CODEX_FRONT_CLAIM_ROOT,
    CodexFrontClaimPolicy,
    build_codex_front_claim,
    close_codex_front_claim,
    write_codex_front_claim,
)
from .codex_report_observer import DEFAULT_CODEX_RECEIPT_LEDGER, CodexReportSelector
from .codex_request import DEFAULT_CODEX_REQUEST_ROOT
from .file_transfer import DEFAULT_QUARANTINE_ROOT, FILE_TRANSFER_CONFIRM_PHRASE
from .mailbox import DEFAULT_CODEX_INBOX_ROOT
from .protocol import SynapsPreparedRequest, SynapsValidationError


CODEX_COORDINATION_SESSION_SCHEMA = "ester.synaps.codex_coordination_session.v1"
CODEX_COORDINATION_SESSION_PLAN_SCHEMA = "ester.synaps.codex_coordination_session.plan.v1"
CODEX_COORDINATION_SESSION_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_COORDINATION_SESSION_RUN"
DEFAULT_CODEX_COORDINATION_SESSION_ROOT = Path("data") / "synaps" / "codex_bridge" / "coordination_sessions"


@dataclass(frozen=True)
class CodexCoordinationSessionPolicy:
    max_steps: int = 4
    max_wall_clock_sec: float = 900.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexCoordinationSessionPolicy":
        source = os.environ if env is None else env
        return cls(
            max_steps=_bounded_int(source.get("SYNAPS_CODEX_COORDINATION_SESSION_MAX_STEPS"), 4, 1, 12),
            max_wall_clock_sec=_bounded_float(
                source.get("SYNAPS_CODEX_COORDINATION_SESSION_MAX_WALL_CLOCK_SEC"),
                900.0,
                1.0,
                3600.0,
            ),
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def load_codex_coordination_session_plan(path: str | Path) -> dict[str, Any]:
    plan_path = Path(path)
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SynapsValidationError("coordination session plan is not valid json") from exc
    if not isinstance(plan, Mapping):
        raise SynapsValidationError("coordination session plan must be an object")
    return dict(plan)


def validate_codex_coordination_session_gate(env: Mapping[str, str], *, confirm: str = "") -> list[str]:
    status = codex_daemon_arm_status(env)
    problems: list[str] = []
    if confirm != CODEX_COORDINATION_SESSION_CONFIRM_PHRASE:
        problems.append("missing_codex_coordination_session_confirm_phrase")
    if not _env_bool(env.get("SYNAPS_CODEX_COORDINATION_SESSION", "0")):
        problems.append("SYNAPS_CODEX_COORDINATION_SESSION_not_enabled")
    if not _env_bool(env.get("SYNAPS_CODEX_COORDINATION_SESSION_ARMED", "0")):
        problems.append("SYNAPS_CODEX_COORDINATION_SESSION_ARMED_not_enabled")
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
    for key in (
        "SISTER_CONVERSATION_WINDOW",
        "SISTER_CONVERSATION_WINDOW_ARMED",
        "SISTER_OPERATOR_GATE",
        "SISTER_OPERATOR_GATE_ARMED",
        "SISTER_SCHEDULE",
        "SISTER_SCHEDULE_ARMED",
    ):
        if _env_bool(env.get(key, "0")):
            problems.append(f"{key}_must_remain_disabled")
    return problems


def run_codex_coordination_session(
    *,
    plan: Mapping[str, Any],
    env: Mapping[str, str] | None = None,
    env_file: str | Path = ".env",
    session_root: str | Path = DEFAULT_CODEX_COORDINATION_SESSION_ROOT,
    confirm: str = "",
    policy: CodexCoordinationSessionPolicy | None = None,
    postcheck_roots: list[str | Path] | None = None,
    sleep_fn=time.sleep,
    time_fn=time.monotonic,
    send_fn: Callable[[SynapsPreparedRequest], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    actual_env = dict(os.environ if env is None else env)
    actual_policy = policy or CodexCoordinationSessionPolicy.from_env(actual_env)
    safe_plan = _safe_plan(plan)
    session_id = _safe_token(str(safe_plan.get("session_id") or safe_plan.get("nonce") or "session"), "session_id")
    operator = _safe_token(str(safe_plan.get("operator") or "codex-coordination-session"), "operator")
    root = Path(session_root)
    started = time_fn()
    output: dict[str, Any] = {
        "schema": CODEX_COORDINATION_SESSION_SCHEMA,
        "ok": True,
        "session_id": session_id,
        "operator": operator,
        "session_root": str(root),
        "persistent": False,
        "auto_ingest": False,
        "memory": "off",
        "policy": actual_policy.to_record(),
        "steps": [],
        "problems": [],
    }
    gate_problems = validate_codex_coordination_session_gate(actual_env, confirm=confirm)
    plan_problems = _plan_problems(safe_plan, actual_policy)
    if gate_problems or plan_problems:
        output["ok"] = False
        output["problems"].extend([*gate_problems, *plan_problems])
        output["result"] = {"ok": False, "status": "session_gate_failed", "problems": output["problems"]}
        return _finish_session(output, root, started, time_fn, actual_policy)

    front_claim_plan = _front_claim_plan(safe_plan)
    front_claim_id = ""
    if front_claim_plan:
        front_claim_payload = _write_session_front_claim(
            front_claim_plan,
            env=actual_env,
            operator=operator,
            now=_utc_now(),
        )
        output["front_claim"] = _redacted(front_claim_payload)
        front_claim_id = str(front_claim_payload.get("claim", {}).get("claim_id") or "")
        if not front_claim_payload.get("ok"):
            output["ok"] = False
            output["problems"].append("front_claim_write_failed")
            output["result"] = {"ok": False, "status": "session_gate_failed", "problems": output["problems"]}
            return _finish_session(output, root, started, time_fn, actual_policy)

    for index, step in enumerate(safe_plan["steps"], start=1):
        if time_fn() - started > actual_policy.max_wall_clock_sec:
            output["ok"] = False
            output["problems"].append("session_max_wall_clock_exceeded")
            break
        step_payload = _run_session_step(
            step=dict(step),
            index=index,
            base_env=actual_env,
            session_id=session_id,
            operator=operator,
            env_file=env_file,
            session_root=root,
            postcheck_roots=postcheck_roots,
            sleep_fn=sleep_fn,
            send_fn=send_fn,
        )
        output["steps"].append(_redacted(step_payload))
        if not step_payload.get("ok"):
            output["ok"] = False
            output["problems"].append(f"step_{index}_failed")
            break

    if front_claim_plan and front_claim_plan.get("close_on_exit", True):
        close_payload = _close_session_front_claim(
            front_claim_plan,
            claim_id=front_claim_id,
            env=actual_env,
            operator=operator,
            status="completed" if output.get("ok") else "failed",
        )
        output["front_claim_close"] = _redacted(close_payload)
        if not close_payload.get("ok"):
            output["ok"] = False
            output["problems"].append("front_claim_close_failed")

    output["result"] = {
        "ok": bool(output.get("ok")),
        "status": "session_complete" if output.get("ok") else "session_failed",
        "step_count": len(output["steps"]),
    }
    return _finish_session(output, root, started, time_fn, actual_policy)


def _run_session_step(
    *,
    step: dict[str, Any],
    index: int,
    base_env: Mapping[str, str],
    session_id: str,
    operator: str,
    env_file: str | Path,
    session_root: Path,
    postcheck_roots: list[str | Path] | None,
    sleep_fn,
    send_fn,
) -> dict[str, Any]:
    phase = str(step.get("phase") or "")
    step_nonce = _safe_token(str(step.get("nonce") or f"{session_id}-{index}-{phase}"), "step_nonce")
    step_operator = _safe_token(str(step.get("operator") or f"{operator}-{index}"), "step_operator")
    step_env = _phase_env(base_env, phase=phase, mutate=bool(step.get("apply") or step.get("send")))
    if phase == PHASE_SEND_FILE and "send_timeout_sec" in step:
        step_env["SISTER_SEND_TIMEOUT_SEC"] = str(_bounded_float(step.get("send_timeout_sec"), 10.0, 0.1, 30.0))
    cycle_policy = CodexCoordinationCyclePolicy(
        max_cycles=_bounded_int(step.get("max_cycles"), 1, 1, 120),
        sleep_sec=_bounded_float(step.get("sleep_sec"), 0.0, 0.0, 300.0),
        max_wall_clock_sec=_bounded_float(step.get("max_wall_clock_sec"), 300.0, 1.0, 3600.0),
        require_exact_for_live_wait=True,
    )
    selector = None
    send_spec = None
    if phase == PHASE_SEND_FILE:
        send_spec = CodexCoordinationSendSpec(
            file_path=str(step.get("file") or ""),
            base_dir=str(step.get("base_dir") or ""),
            kind=str(step.get("kind") or "codex_contract"),
            note=str(step.get("note") or ""),
            include_payload=bool(step.get("include_payload", True)),
        )
    elif phase == PHASE_WAIT_CONTRACT:
        selector = CodexCoordinationSelector(
            expected_name=str(step.get("expect_name") or ""),
            expected_kind=str(step.get("expect_kind") or "codex_contract"),
            expected_sender=str(step.get("expect_sender") or ""),
            note_contains=str(step.get("note_contains") or ""),
            expected_sha256=str(step.get("expect_sha256") or ""),
            expected_size=_optional_int(step.get("expect_size")),
        )
    elif phase == PHASE_WAIT_REPORT:
        selector = CodexReportSelector(
            expected_name=str(step.get("expect_name") or ""),
            expected_sender=str(step.get("expect_sender") or ""),
            note_contains=str(step.get("note_contains") or ""),
            expected_sha256=str(step.get("expect_sha256") or ""),
            expected_size=_optional_int(step.get("expect_size")),
            expected_name_aliases=tuple(str(item) for item in list(step.get("expect_name_aliases") or [])[:5]),
        )
    cycle_root = Path(str(step.get("cycle_root") or (session_root / session_id / f"{index:02d}_{phase}")))
    return run_codex_coordination_cycle_phase(
        phase=phase,
        nonce=step_nonce,
        operator=step_operator,
        env=step_env,
        env_file=env_file,
        cycle_root=cycle_root,
        selector=selector,
        send_spec=send_spec,
        apply=bool(step.get("apply")),
        send=bool(step.get("send")),
        confirm=CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
        send_confirm=FILE_TRANSFER_CONFIRM_PHRASE if step.get("send") else "",
        policy=cycle_policy,
        scanner_root=step.get("scanner_root") or (session_root / session_id / "scanner"),
        quarantine_root=step.get("quarantine_root") or DEFAULT_QUARANTINE_ROOT,
        inbox_root=step.get("inbox_root") or DEFAULT_CODEX_INBOX_ROOT,
        daemon_root=step.get("daemon_root") or DEFAULT_CODEX_DAEMON_ROOT,
        receipt_ledger=step.get("receipt_ledger") or DEFAULT_CODEX_RECEIPT_LEDGER,
        request_root=step.get("request_root") or DEFAULT_CODEX_REQUEST_ROOT,
        postcheck_roots=postcheck_roots,
        sleep_fn=sleep_fn,
        send_fn=send_fn,
    )


def _phase_env(base_env: Mapping[str, str], *, phase: str, mutate: bool) -> dict[str, str]:
    env = dict(base_env)
    forced_zero = {
        "SISTER_AUTOCHAT",
        "SISTER_CONVERSATION_WINDOW",
        "SISTER_CONVERSATION_WINDOW_ARMED",
        "SISTER_OPERATOR_GATE",
        "SISTER_OPERATOR_GATE_ARMED",
        "SISTER_SCHEDULE",
        "SISTER_SCHEDULE_ARMED",
        "SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX",
        "SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS",
        "SYNAPS_CODEX_DAEMON_RUNNER",
        "SYNAPS_CODEX_DAEMON_RUNNER_ARMED",
        "SYNAPS_CODEX_DAEMON_PERSISTENT",
        "SYNAPS_CODEX_DAEMON_PERSISTENT_ARMED",
        "SYNAPS_CODEX_DAEMON_KILL_SWITCH",
    }
    for key in forced_zero:
        env[key] = "0"
    env["SYNAPS_CODEX_COORDINATION_CYCLE"] = "1"
    env["SYNAPS_CODEX_COORDINATION_CYCLE_ARMED"] = "1"
    env["SISTER_FILE_TRANSFER"] = "1" if phase == PHASE_SEND_FILE and mutate else "0"
    env["SISTER_FILE_TRANSFER_ARMED"] = "1" if phase == PHASE_SEND_FILE and mutate else "0"
    env["SYNAPS_CODEX_COORDINATION_SCANNER"] = "1" if phase == PHASE_WAIT_CONTRACT else "0"
    env["SYNAPS_CODEX_COORDINATION_SCANNER_ARMED"] = "1" if phase == PHASE_WAIT_CONTRACT else "0"
    wait_report = phase == PHASE_WAIT_REPORT
    env["SYNAPS_CODEX_DAEMON"] = "1" if wait_report else "0"
    env["SYNAPS_CODEX_DAEMON_ARMED"] = "1" if wait_report else "0"
    env["SYNAPS_CODEX_DAEMON_OBSERVE_REPORTS"] = "1" if wait_report else "0"
    env["SYNAPS_CODEX_DAEMON_OBSERVE_REPORTS_ARMED"] = "1" if wait_report else "0"
    return env


def _safe_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("schema") not in {CODEX_COORDINATION_SESSION_PLAN_SCHEMA, None, ""}:
        raise SynapsValidationError("unsupported coordination session plan schema")
    steps = plan.get("steps")
    if not isinstance(steps, list):
        raise SynapsValidationError("coordination session steps must be a list")
    return {**dict(plan), "steps": [dict(step) for step in steps if isinstance(step, Mapping)]}


def _plan_problems(plan: Mapping[str, Any], policy: CodexCoordinationSessionPolicy) -> list[str]:
    steps = list(plan.get("steps") or [])
    problems: list[str] = []
    if not steps:
        problems.append("coordination_session_steps_required")
    if len(steps) > policy.max_steps:
        problems.append("coordination_session_too_many_steps")
    for index, step in enumerate(steps, start=1):
        phase = str(step.get("phase") or "")
        if phase not in {PHASE_SEND_FILE, PHASE_WAIT_CONTRACT, PHASE_WAIT_REPORT}:
            problems.append(f"step_{index}_unknown_phase")
        if phase == PHASE_SEND_FILE and bool(step.get("send")) and not bool(step.get("include_payload", True)):
            problems.append(f"step_{index}_send_requires_include_payload")
        if phase in {PHASE_WAIT_CONTRACT, PHASE_WAIT_REPORT} and bool(step.get("apply")):
            if len(str(step.get("expect_sha256") or "")) != 64:
                problems.append(f"step_{index}_expected_sha256_required")
            if _optional_int(step.get("expect_size")) is None:
                problems.append(f"step_{index}_expected_size_required")
    front_claim = plan.get("front_claim")
    if front_claim not in (None, "", False):
        if not isinstance(front_claim, Mapping):
            problems.append("front_claim_must_be_object")
        else:
            expected = _front_claim_expected_report(front_claim)
            for key in ("front_id", "owner", "marker"):
                if not str(front_claim.get(key) or "").strip():
                    problems.append(f"front_claim_{key}_required")
            if not expected.get("name"):
                problems.append("front_claim_expected_name_required")
            if len(str(expected.get("sha256") or "")) != 64:
                problems.append("front_claim_expected_sha256_required")
            if _optional_int(expected.get("size")) is None:
                problems.append("front_claim_expected_size_required")
    return problems


def _front_claim_plan(plan: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = plan.get("front_claim")
    if raw in (None, "", False):
        return None
    return dict(raw)


def _front_claim_expected_report(front_claim: Mapping[str, Any]) -> dict[str, Any]:
    nested = front_claim.get("expected_report")
    if isinstance(nested, Mapping):
        return dict(nested)
    return {
        "name": front_claim.get("expect_name") or "",
        "sender": front_claim.get("expect_sender") or "",
        "note_contains": front_claim.get("expect_note_contains") or front_claim.get("note_contains") or "",
        "sha256": front_claim.get("expect_sha256") or "",
        "size": front_claim.get("expect_size") if "expect_size" in front_claim else None,
        "kind": front_claim.get("expect_kind") or "codex_report",
    }


def _front_claim_env(base_env: Mapping[str, str]) -> dict[str, str]:
    env = dict(base_env)
    for key in (
        "SISTER_AUTOCHAT",
        "SISTER_CONVERSATION_WINDOW",
        "SISTER_CONVERSATION_WINDOW_ARMED",
        "SISTER_OPERATOR_GATE",
        "SISTER_OPERATOR_GATE_ARMED",
        "SISTER_SCHEDULE",
        "SISTER_SCHEDULE_ARMED",
        "SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX",
        "SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS",
        "SYNAPS_CODEX_DAEMON_RUNNER",
        "SYNAPS_CODEX_DAEMON_RUNNER_ARMED",
        "SYNAPS_CODEX_DAEMON_PERSISTENT",
        "SYNAPS_CODEX_DAEMON_PERSISTENT_ARMED",
        "SYNAPS_CODEX_DAEMON_KILL_SWITCH",
    ):
        env[key] = "0"
    return env


def _write_session_front_claim(
    front_claim: Mapping[str, Any],
    *,
    env: Mapping[str, str],
    operator: str,
    now: str,
) -> dict[str, Any]:
    claim_env = _front_claim_env(env)
    claim = build_codex_front_claim(
        front_id=str(front_claim.get("front_id") or ""),
        owner=str(front_claim.get("owner") or operator),
        marker=str(front_claim.get("marker") or ""),
        title=str(front_claim.get("title") or ""),
        status=str(front_claim.get("status") or "claimed"),
        lease_seconds=_bounded_int(front_claim.get("lease_sec"), 1800, 60, 24 * 3600),
        supersedes=[str(item) for item in list(front_claim.get("supersedes") or [])[:8]],
        expected_report=_front_claim_expected_report(front_claim),
        created_at=now,
    )
    return write_codex_front_claim(
        claim,
        env=claim_env,
        root=front_claim.get("root") or DEFAULT_CODEX_FRONT_CLAIM_ROOT,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CONFIRM_PHRASE,
        operator=operator,
        policy=CodexFrontClaimPolicy.from_env(claim_env),
    )


def _close_session_front_claim(
    front_claim: Mapping[str, Any],
    *,
    claim_id: str,
    env: Mapping[str, str],
    operator: str,
    status: str,
) -> dict[str, Any]:
    claim_env = _front_claim_env(env)
    return close_codex_front_claim(
        claim_id,
        status=status,
        reason=str(front_claim.get("close_reason") or "coordination session finished"),
        env=claim_env,
        root=front_claim.get("root") or DEFAULT_CODEX_FRONT_CLAIM_ROOT,
        apply=True,
        confirm=CODEX_FRONT_CLAIM_CLOSE_CONFIRM_PHRASE,
        operator=operator,
        policy=CodexFrontClaimPolicy.from_env(claim_env),
    )


def _finish_session(
    payload: dict[str, Any],
    root: Path,
    started: float,
    time_fn,
    policy: CodexCoordinationSessionPolicy,
) -> dict[str, Any]:
    payload["elapsed_sec"] = round(max(0.0, float(time_fn() - started)), 3)
    if payload["elapsed_sec"] > policy.max_wall_clock_sec:
        payload["ok"] = False
        payload.setdefault("problems", []).append("session_max_wall_clock_exceeded")
    redaction_problems = _redaction_problems(payload)
    if redaction_problems:
        payload["ok"] = False
        payload.setdefault("problems", []).extend(redaction_problems)
    _append_jsonl(root / "events.jsonl", _redacted(payload))
    return payload


def _redacted(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"payload_b64", "token", "content"}:
                continue
            out[key] = _redacted(item)
        return out
    if isinstance(value, list):
        return [_redacted(item) for item in value]
    if isinstance(value, str):
        return value[:600]
    return value


def _redaction_problems(payload: Mapping[str, Any]) -> list[str]:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    problems: list[str] = []
    if "payload_b64" in text:
        problems.append("payload_b64_leaked_to_session_output")
    if '"token"' in text or "sync_token" in text or "SISTER_SYNC_TOKEN" in text:
        problems.append("token_leaked_to_session_output")
    return problems


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"created_at": _utc_now(), **dict(record)}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return max(0, int(value))


def _safe_token(raw: str, label: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(raw or "").strip()).strip("-_")
    if not safe:
        raise SynapsValidationError(f"{label} is required")
    return safe[:120]


def _env_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def _bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
