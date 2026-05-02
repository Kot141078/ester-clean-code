"""Dry-run-first Codex worker sandbox preflight.

The preflight is a local diagnostic, not a daemon and not a task runner. It can
run one read-only `codex exec` probe only when explicitly armed. The result is a
capability signal for future runner-window gates, not an invitation to bypass
the sandbox.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .codex_daemon import (
    CODEX_WORKER_SANDBOX_BLOCKED_REASON,
    codex_daemon_arm_status,
    _redact,
    _resolve_command_prefix,
    _worker_sandbox_blocked,
)
from .protocol import SynapsValidationError


CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_WORKER_PREFLIGHT"
CODEX_WORKER_PREFLIGHT_EVENT_SCHEMA = "ester.synaps.codex_worker_preflight_event.v1"
CODEX_WORKER_PREFLIGHT_MODE = "codex_worker_preflight"
DEFAULT_CODEX_WORKER_PREFLIGHT_ROOT = Path("data") / "synaps" / "codex_bridge" / "worker_preflight"


@dataclass(frozen=True)
class CodexWorkerPreflightPolicy:
    workdir: str = "."
    codex_command: str = "codex"
    sandbox: str = "read-only"
    timeout_sec: int = 180
    max_output_chars: int = 3000
    target_file: str = "modules/synaps/codex_daemon.py"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexWorkerPreflightPolicy":
        source = os.environ if env is None else env
        return cls(
            workdir=str(source.get("SYNAPS_CODEX_WORKER_PREFLIGHT_WORKDIR") or "."),
            codex_command=str(source.get("SYNAPS_CODEX_COMMAND") or "codex"),
            sandbox=str(source.get("SYNAPS_CODEX_WORKER_PREFLIGHT_SANDBOX") or "read-only"),
            timeout_sec=_bounded_int(source.get("SYNAPS_CODEX_WORKER_PREFLIGHT_TIMEOUT_SEC"), 180, 30, 900),
            max_output_chars=_bounded_int(source.get("SYNAPS_CODEX_WORKER_PREFLIGHT_MAX_OUTPUT_CHARS"), 3000, 200, 12000),
            target_file=str(source.get("SYNAPS_CODEX_WORKER_PREFLIGHT_TARGET") or "modules/synaps/codex_daemon.py"),
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def codex_worker_preflight_arm_status(env: Mapping[str, str]) -> dict[str, bool]:
    daemon_status = codex_daemon_arm_status(env)
    return {
        "preflight": _env_bool(env.get("SYNAPS_CODEX_WORKER_PREFLIGHT", "0")),
        "armed": _env_bool(env.get("SYNAPS_CODEX_WORKER_PREFLIGHT_ARMED", "0")),
        "kill_switch": _env_bool(env.get("SYNAPS_CODEX_WORKER_PREFLIGHT_KILL_SWITCH", "0"))
        or daemon_status["kill_switch"],
        "legacy_autochat": daemon_status["legacy_autochat"],
        "daemon": daemon_status["daemon"],
        "daemon_armed": daemon_status["armed"],
        "persistent": daemon_status["persistent"],
        "persistent_armed": daemon_status["persistent_armed"],
        "promote_mailbox": daemon_status["promote_mailbox"],
        "enqueue_handoffs": daemon_status["enqueue_handoffs"],
        "daemon_runner": daemon_status["runner"],
        "daemon_runner_armed": daemon_status["runner_armed"],
        "runner_window": _env_bool(env.get("SYNAPS_CODEX_RUNNER_WINDOW", "0")),
        "scheduler": _env_bool(env.get("SISTER_SCHEDULE", "0")),
        "conversation_window": _env_bool(env.get("SISTER_CONVERSATION_WINDOW", "0")),
        "file_transfer": _env_bool(env.get("SISTER_FILE_TRANSFER", "0")),
    }


def validate_codex_worker_preflight_gate(
    env: Mapping[str, str],
    confirm: str,
    policy: CodexWorkerPreflightPolicy,
) -> list[str]:
    status = codex_worker_preflight_arm_status(env)
    problems: list[str] = []
    if confirm != CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE:
        problems.append("missing_codex_worker_preflight_confirm_phrase")
    if not status["preflight"]:
        problems.append("SYNAPS_CODEX_WORKER_PREFLIGHT_not_enabled")
    if not status["armed"]:
        problems.append("SYNAPS_CODEX_WORKER_PREFLIGHT_ARMED_not_enabled")
    if status["kill_switch"]:
        problems.append("SYNAPS_CODEX_WORKER_PREFLIGHT_KILL_SWITCH_enabled")
    if status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    if (
        status["daemon"]
        or status["daemon_armed"]
        or status["persistent"]
        or status["persistent_armed"]
        or status["promote_mailbox"]
        or status["enqueue_handoffs"]
        or status["daemon_runner"]
        or status["daemon_runner_armed"]
        or status["runner_window"]
    ):
        problems.append("SYNAPS_CODEX_daemon_runner_flags_must_remain_disabled_for_preflight")
    if status["scheduler"] or status["conversation_window"] or status["file_transfer"]:
        problems.append("SYNAPS_live_send_flags_must_remain_disabled_for_preflight")
    if str(policy.sandbox or "").strip().lower() != "read-only":
        problems.append("SYNAPS_CODEX_WORKER_PREFLIGHT_SANDBOX_must_be_read_only")
    return problems


def run_codex_worker_preflight(
    *,
    env: Mapping[str, str],
    apply: bool = False,
    confirm: str = "",
    operator: str = "codex-worker-preflight",
    preflight_id: str | None = None,
    root: str | Path = DEFAULT_CODEX_WORKER_PREFLIGHT_ROOT,
    policy: CodexWorkerPreflightPolicy | None = None,
) -> dict[str, Any]:
    resolved_policy = policy or CodexWorkerPreflightPolicy.from_env(env)
    safe_id = _safe_identifier(preflight_id or f"synaps-codex-worker-preflight-{uuid4()}")
    status = codex_worker_preflight_arm_status(env)
    output: dict[str, Any] = {
        "ok": True,
        "dry_run": not apply,
        "mode": CODEX_WORKER_PREFLIGHT_MODE,
        "preflight_id": safe_id,
        "confirm_required": CODEX_WORKER_PREFLIGHT_CONFIRM_PHRASE,
        "arm_status": status,
        "policy": resolved_policy.to_record(),
        "auto_ingest": False,
        "memory": "off",
    }

    if not apply:
        return output

    problems = validate_codex_worker_preflight_gate(env, confirm, resolved_policy)
    if problems:
        output["ok"] = False
        output["result"] = {"ok": False, "status": "gate_failed", "problems": problems}
        return output

    run_dir = Path(root) / safe_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        output["ok"] = False
        output["result"] = {"ok": False, "status": "preflight_id_exists"}
        return output
    prompt_path = run_dir / "prompt.md"
    output_path = run_dir / "last_message.md"
    prompt_path.write_text(_preflight_prompt(resolved_policy.target_file), encoding="utf-8")
    result = _run_preflight_codex(resolved_policy, prompt_path, output_path, run_dir)
    result["status"] = _classify_preflight_result(result)
    result["ok"] = result["status"] == "available"
    (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    _append_event(
        Path(root) / "events.jsonl",
        {
            "event": "preflight_finished",
            "operator": operator,
            "preflight_id": safe_id,
            "status": result["status"],
            "returncode": result["returncode"],
        },
    )
    output["result"] = result
    output["ok"] = True
    return output


def _run_preflight_codex(
    policy: CodexWorkerPreflightPolicy,
    prompt_path: Path,
    output_path: Path,
    run_dir: Path,
) -> dict[str, Any]:
    command = _resolve_command_prefix(policy.codex_command) + [
        "exec",
        "--ephemeral",
        "--ignore-rules",
        "--cd",
        str(Path(policy.workdir).resolve()),
        "--sandbox",
        "read-only",
        "--output-last-message",
        str(output_path),
        "-",
    ]
    try:
        proc = subprocess.run(
            command,
            input=prompt_path.read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            timeout=policy.timeout_sec,
            cwd=str(Path(policy.workdir).resolve()),
        )
        stdout = _redact(_preview(proc.stdout, policy.max_output_chars))
        stderr = _redact(_preview(proc.stderr, policy.max_output_chars))
        last_message = ""
        if output_path.is_file():
            last_message = _redact(_preview(output_path.read_text(encoding="utf-8", errors="replace"), policy.max_output_chars))
        (run_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
        (run_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
        return {
            "returncode": int(proc.returncode),
            "stdout": stdout,
            "stderr": stderr,
            "last_message": last_message,
            "blocked_reason": CODEX_WORKER_SANDBOX_BLOCKED_REASON if _worker_sandbox_blocked(stdout, stderr, last_message) else "",
        }
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "timeout", "last_message": "", "blocked_reason": "worker_timeout"}
    except Exception as exc:
        return {"returncode": 1, "stdout": "", "stderr": exc.__class__.__name__, "last_message": "", "blocked_reason": "worker_launch_failed"}


def _classify_preflight_result(result: Mapping[str, Any]) -> str:
    if result.get("blocked_reason") == CODEX_WORKER_SANDBOX_BLOCKED_REASON:
        return "worker_sandbox_blocked"
    if result.get("blocked_reason"):
        return str(result["blocked_reason"])
    if int(result.get("returncode") or 0) != 0:
        return "worker_failed"
    return "available"


def _preflight_prompt(target_file: str) -> str:
    return "\n".join(
        [
            "You are a SYNAPS Codex worker preflight probe.",
            "Read-only task: inspect only the repo-local target file named below.",
            "Do not read .codex memories, .codex sessions, .env, memory/passport/vector/chroma/RAG, or any live SYNAPS state.",
            "Do not edit files. Do not run tests. Do not run live sends.",
            f"Target file: {target_file}",
            "If the file can be inspected, end with exact line: CODEX_WORKER_PREFLIGHT_AVAILABLE.",
            "If blocked, report the blocker and end with exact line: CODEX_WORKER_PREFLIGHT_BLOCKED.",
        ]
    )


def _append_event(path: Path, event: Mapping[str, Any]) -> None:
    record = {
        "schema": CODEX_WORKER_PREFLIGHT_EVENT_SCHEMA,
        "created_at": _iso_now(),
        "auto_ingest": False,
        "memory": "off",
        **dict(event),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _bounded_int(raw: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(raw if raw is not None else default).strip())
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


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


def _preview(text: str, limit: int) -> str:
    return str(text or "")[:limit]
