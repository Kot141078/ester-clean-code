"""Bounded runner for SYNAPS Codex coordination session ticks.

This is intentionally not a daemon. It runs a finite number of one-shot ticks
under a lease, records redacted summaries, and exits.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .codex_coordination_session_tick import (
    CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
    DEFAULT_CODEX_COORDINATION_SESSION_PLAN_COMPLETED,
    DEFAULT_CODEX_COORDINATION_SESSION_PLAN_FAILED,
    DEFAULT_CODEX_COORDINATION_SESSION_PLAN_QUEUE,
    DEFAULT_CODEX_COORDINATION_SESSION_TICK_LEDGER,
    CodexCoordinationSessionPlanSelector,
    CodexCoordinationSessionTickPolicy,
    run_codex_coordination_session_tick,
)
from .codex_daemon import codex_daemon_arm_status


CODEX_COORDINATION_TICK_RUNNER_SCHEMA = "ester.synaps.codex_coordination_tick_runner.v1"
CODEX_COORDINATION_TICK_RUNNER_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_COORDINATION_TICK_RUNNER_RUN"
DEFAULT_CODEX_COORDINATION_TICK_RUNNER_ROOT = Path("data") / "synaps" / "codex_bridge" / "coordination_tick_runner"
DEFAULT_CODEX_COORDINATION_TICK_RUNNER_LEDGER = DEFAULT_CODEX_COORDINATION_TICK_RUNNER_ROOT / "events.jsonl"


@dataclass(frozen=True)
class CodexCoordinationTickRunnerPolicy:
    max_ticks: int = 1
    max_runtime_sec: float = 300.0
    sleep_sec: float = 0.0
    continue_on_no_work: bool = False
    postcheck_max_file_bytes: int = 1024 * 1024

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexCoordinationTickRunnerPolicy":
        source = os.environ if env is None else env
        return cls(
            max_ticks=_bounded_int(source.get("SYNAPS_CODEX_COORDINATION_TICK_RUNNER_MAX_TICKS"), 1, 1, 50),
            max_runtime_sec=_bounded_float(
                source.get("SYNAPS_CODEX_COORDINATION_TICK_RUNNER_MAX_RUNTIME_SEC"),
                300.0,
                1.0,
                3600.0,
            ),
            sleep_sec=_bounded_float(source.get("SYNAPS_CODEX_COORDINATION_TICK_RUNNER_SLEEP_SEC"), 0.0, 0.0, 300.0),
            continue_on_no_work=_env_bool(source.get("SYNAPS_CODEX_COORDINATION_TICK_RUNNER_CONTINUE_ON_NO_WORK", "0")),
            postcheck_max_file_bytes=_bounded_int(
                source.get("SYNAPS_CODEX_COORDINATION_TICK_RUNNER_POSTCHECK_MAX_FILE_BYTES"),
                1024 * 1024,
                1024,
                5 * 1024 * 1024,
            ),
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def validate_codex_coordination_tick_runner_gate(env: Mapping[str, str], *, confirm: str = "") -> list[str]:
    status = codex_daemon_arm_status(env)
    problems: list[str] = []
    if confirm != CODEX_COORDINATION_TICK_RUNNER_CONFIRM_PHRASE:
        problems.append("missing_codex_coordination_tick_runner_confirm_phrase")
    if not _env_bool(env.get("SYNAPS_CODEX_COORDINATION_TICK_RUNNER", "0")):
        problems.append("SYNAPS_CODEX_COORDINATION_TICK_RUNNER_not_enabled")
    if not _env_bool(env.get("SYNAPS_CODEX_COORDINATION_TICK_RUNNER_ARMED", "0")):
        problems.append("SYNAPS_CODEX_COORDINATION_TICK_RUNNER_ARMED_not_enabled")
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


def run_codex_coordination_tick_runner(
    *,
    env: Mapping[str, str] | None = None,
    env_file: str | Path = ".env",
    queue_root: str | Path = DEFAULT_CODEX_COORDINATION_SESSION_PLAN_QUEUE,
    completed_root: str | Path = DEFAULT_CODEX_COORDINATION_SESSION_PLAN_COMPLETED,
    failed_root: str | Path = DEFAULT_CODEX_COORDINATION_SESSION_PLAN_FAILED,
    tick_ledger_path: str | Path = DEFAULT_CODEX_COORDINATION_SESSION_TICK_LEDGER,
    runner_ledger_path: str | Path = DEFAULT_CODEX_COORDINATION_TICK_RUNNER_LEDGER,
    session_root: str | Path = Path("data") / "synaps" / "codex_bridge" / "coordination_sessions",
    selector: CodexCoordinationSessionPlanSelector | None = None,
    confirm: str = "",
    policy: CodexCoordinationTickRunnerPolicy | None = None,
    tick_policy: CodexCoordinationSessionTickPolicy | None = None,
    postcheck_roots: list[str | Path] | None = None,
    tick_fn: Callable[..., dict[str, Any]] = run_codex_coordination_session_tick,
    sleep_fn=time.sleep,
    time_fn=time.monotonic,
) -> dict[str, Any]:
    actual_env = dict(os.environ if env is None else env)
    actual_policy = policy or CodexCoordinationTickRunnerPolicy.from_env(actual_env)
    started = time_fn()
    env_path = Path(env_file) if str(env_file or "") else None
    env_before = _fingerprint_optional(env_path)
    runner_ledger = Path(runner_ledger_path).resolve()
    output: dict[str, Any] = {
        "schema": CODEX_COORDINATION_TICK_RUNNER_SCHEMA,
        "ok": True,
        "persistent": False,
        "auto_ingest": False,
        "memory": "off",
        "policy": actual_policy.to_record(),
        "ticks": [],
        "problems": [],
    }
    gate_problems = validate_codex_coordination_tick_runner_gate(actual_env, confirm=confirm)
    if gate_problems:
        output["ok"] = False
        output["problems"].extend(gate_problems)
        output["result"] = {"ok": False, "status": "runner_gate_failed", "problems": gate_problems}
        return output

    lock_path = runner_ledger.parent / "locks" / "bounded_tick_runner.lock"
    lock_acquired = False
    try:
        _acquire_lock(lock_path)
        lock_acquired = True
        for index in range(1, actual_policy.max_ticks + 1):
            if time_fn() - started > actual_policy.max_runtime_sec:
                output["ok"] = False
                output["problems"].append("max_runtime_exceeded")
                output["result"] = {"ok": False, "status": "max_runtime_exceeded"}
                break
            if _fingerprint_optional(env_path) != env_before:
                output["ok"] = False
                output["problems"].append("env_file_changed")
                output["result"] = {"ok": False, "status": "env_file_changed"}
                break
            if _env_bool(actual_env.get("SYNAPS_CODEX_DAEMON_KILL_SWITCH", "0")):
                output["ok"] = False
                output["problems"].append("kill_switch_enabled")
                output["result"] = {"ok": False, "status": "kill_switch_enabled"}
                break

            tick_env = dict(actual_env)
            tick_env["SYNAPS_CODEX_COORDINATION_SESSION_TICK"] = "1"
            tick_env["SYNAPS_CODEX_COORDINATION_SESSION_TICK_ARMED"] = "1"
            tick_payload = tick_fn(
                env=tick_env,
                env_file=env_file,
                queue_root=queue_root,
                completed_root=completed_root,
                failed_root=failed_root,
                ledger_path=tick_ledger_path,
                session_root=session_root,
                selector=selector,
                confirm=CODEX_COORDINATION_SESSION_TICK_CONFIRM_PHRASE,
                policy=tick_policy or CodexCoordinationSessionTickPolicy.from_env(tick_env),
                postcheck_roots=postcheck_roots,
            )
            summary = _tick_summary(index, tick_payload)
            output["ticks"].append(summary)
            _append_jsonl(runner_ledger, {"event": "tick", "created_at": _utc_now(), **summary})
            if not tick_payload.get("ok"):
                output["ok"] = False
                output["result"] = {"ok": False, "status": "tick_failed", "tick_index": index}
                break
            tick_status = str((tick_payload.get("result") or {}).get("status") or "")
            if tick_status == "no_queued_plan" and not actual_policy.continue_on_no_work:
                output["result"] = {"ok": True, "status": "no_queued_plan", "tick_index": index}
                break
            if index < actual_policy.max_ticks and actual_policy.sleep_sec:
                sleep_fn(actual_policy.sleep_sec)
        else:
            output["result"] = {"ok": True, "status": "max_ticks_reached"}
    except Exception as exc:
        output["ok"] = False
        output["problems"].append(str(exc))
        output["result"] = {"ok": False, "status": "runner_failed", "error": exc.__class__.__name__}
    finally:
        if lock_acquired:
            _release_lock(lock_path)

    output["elapsed_sec"] = round(time_fn() - started, 3)
    redaction_problems = _redaction_problems(output, runner_ledger, actual_env)
    if redaction_problems:
        output["ok"] = False
        output["problems"].extend(redaction_problems)
        output["result"] = {"ok": False, "status": "redaction_failed", "problems": redaction_problems}
    return output


def _tick_summary(index: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    result = payload.get("result") if isinstance(payload.get("result"), Mapping) else {}
    selected = payload.get("selected_plan") if isinstance(payload.get("selected_plan"), Mapping) else {}
    return {
        "tick_index": index,
        "ok": bool(payload.get("ok")),
        "status": str(result.get("status") or ""),
        "candidate_count": int(payload.get("candidate_count") or 0),
        "selected_plan": str(selected.get("name") or ""),
        "mark_status": str((payload.get("mark") or {}).get("status") if isinstance(payload.get("mark"), Mapping) else ""),
    }


def _acquire_lock(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump({"created_at": _utc_now(), "pid": os.getpid()}, stream, sort_keys=True)


def _release_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


def _fingerprint_optional(path: Path | None) -> dict[str, Any] | None:
    if path is None or not str(path).strip() or not path.exists():
        return None
    stat = path.stat()
    return {"path": str(path.resolve()), "mtime_ns": stat.st_mtime_ns, "size": stat.st_size}


def _redaction_problems(payload: Mapping[str, Any], ledger: Path, env: Mapping[str, str]) -> list[str]:
    token = str(env.get("SISTER_SYNC_TOKEN") or "")
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if ledger.exists():
        text += ledger.read_text(encoding="utf-8", errors="ignore")
    problems: list[str] = []
    if "payload_b64" in text:
        problems.append("payload_b64_leaked_to_runner_output")
    if '"token"' in text or "SISTER_SYNC_TOKEN" in text or (token and token in text):
        problems.append("token_leaked_to_runner_output")
    if '"content"' in text:
        problems.append("content_leaked_to_runner_output")
    return problems


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_bool(raw: str | None) -> bool:
    return str(raw or "0").strip().lower() in {"1", "true", "yes", "on", "y"}


def _bounded_int(raw: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(raw if raw is not None else default).strip())
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _bounded_float(raw: str | None, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(str(raw if raw is not None else default).strip())
    except Exception:
        value = default
    return max(minimum, min(maximum, value))
