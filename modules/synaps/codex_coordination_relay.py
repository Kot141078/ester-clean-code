"""Bounded SYNAPS Codex relay orchestration.

The relay is a small non-persistent wrapper around coordination sessions. It
turns a compact send/wait/respond/final-wait plan into the explicit session plan
that the lower layer already knows how to execute safely.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .codex_coordination_session import (
    CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
    CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
    CodexCoordinationSessionPolicy,
    run_codex_coordination_session,
)
from .codex_daemon import codex_daemon_arm_status
from .protocol import SynapsValidationError


CODEX_COORDINATION_RELAY_SCHEMA = "ester.synaps.codex_coordination_relay.v1"
CODEX_COORDINATION_RELAY_PLAN_SCHEMA = "ester.synaps.codex_coordination_relay.plan.v1"
CODEX_COORDINATION_RELAY_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_COORDINATION_RELAY_RUN"
DEFAULT_CODEX_COORDINATION_RELAY_ROOT = Path("data") / "synaps" / "codex_bridge" / "coordination_relays"


@dataclass(frozen=True)
class CodexCoordinationRelayPolicy:
    max_steps: int = 4
    max_wall_clock_sec: float = 1000.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexCoordinationRelayPolicy":
        source = os.environ if env is None else env
        return cls(
            max_steps=_bounded_int(source.get("SYNAPS_CODEX_COORDINATION_RELAY_MAX_STEPS"), 4, 4, 4),
            max_wall_clock_sec=_bounded_float(
                source.get("SYNAPS_CODEX_COORDINATION_RELAY_MAX_WALL_CLOCK_SEC"),
                1000.0,
                1.0,
                3600.0,
            ),
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def load_codex_coordination_relay_plan(path: str | Path) -> dict[str, Any]:
    plan_path = Path(path)
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SynapsValidationError("coordination relay plan is not valid json") from exc
    if not isinstance(plan, Mapping):
        raise SynapsValidationError("coordination relay plan must be an object")
    return dict(plan)


def validate_codex_coordination_relay_gate(env: Mapping[str, str], *, confirm: str = "") -> list[str]:
    status = codex_daemon_arm_status(env)
    problems: list[str] = []
    if confirm != CODEX_COORDINATION_RELAY_CONFIRM_PHRASE:
        problems.append("missing_codex_coordination_relay_confirm_phrase")
    if not _env_bool(env.get("SYNAPS_CODEX_COORDINATION_RELAY", "0")):
        problems.append("SYNAPS_CODEX_COORDINATION_RELAY_not_enabled")
    if not _env_bool(env.get("SYNAPS_CODEX_COORDINATION_RELAY_ARMED", "0")):
        problems.append("SYNAPS_CODEX_COORDINATION_RELAY_ARMED_not_enabled")
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
        "SISTER_AUTOCHAT",
        "SISTER_CONVERSATION_WINDOW",
        "SISTER_CONVERSATION_WINDOW_ARMED",
        "SISTER_OPERATOR_GATE",
        "SISTER_OPERATOR_GATE_ARMED",
        "SISTER_SCHEDULE",
        "SISTER_SCHEDULE_ARMED",
    ):
        if _env_bool(env.get(key, "0")):
            problems.append(f"{key}_must_remain_disabled")
    return sorted(set(problems))


def build_codex_coordination_relay_session_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    relay_plan = _safe_relay_plan(plan)
    relay_id = _safe_token(str(relay_plan.get("relay_id") or relay_plan.get("session_id") or "relay"), "relay_id")
    operator = _safe_token(str(relay_plan.get("operator") or "codex-coordination-relay"), "operator")
    marker = str(relay_plan.get("marker") or relay_plan.get("note") or "").strip()
    if not marker:
        raise SynapsValidationError("relay marker is required")

    request = _mapping(relay_plan, "request")
    contract = _mapping(relay_plan, "contract")
    response = _mapping(relay_plan, "response")
    final_report = _mapping(relay_plan, "final_report")

    return {
        "schema": CODEX_COORDINATION_SESSION_PLAN_SCHEMA,
        "session_id": relay_id,
        "operator": operator,
        "steps": [
            _send_step(request, default_nonce=f"{relay_id}-send-request", default_kind="codex_contract", default_note=marker),
            _wait_contract_step(contract, default_nonce=f"{relay_id}-wait-contract", default_note=marker),
            _send_step(response, default_nonce=f"{relay_id}-send-response", default_kind="codex_report", default_note=marker),
            _wait_report_step(final_report, default_nonce=f"{relay_id}-wait-final", default_note=marker),
        ],
    }


def dry_run_codex_coordination_relay(plan: Mapping[str, Any]) -> dict[str, Any]:
    session_plan = build_codex_coordination_relay_session_plan(plan)
    payload: dict[str, Any] = {
        "schema": CODEX_COORDINATION_RELAY_SCHEMA,
        "ok": True,
        "dry_run": True,
        "persistent": False,
        "auto_ingest": False,
        "memory": "off",
        "relay_id": session_plan["session_id"],
        "step_count": len(session_plan["steps"]),
        "session_plan": _redacted(session_plan),
        "problems": [],
        "result": {"ok": True, "status": "relay_plan_built"},
    }
    redaction = _redaction_problems(payload, {})
    if redaction:
        payload["ok"] = False
        payload["problems"].extend(redaction)
        payload["result"] = {"ok": False, "status": "redaction_failed", "problems": redaction}
    return payload


def run_codex_coordination_relay(
    *,
    plan: Mapping[str, Any],
    env: Mapping[str, str] | None = None,
    env_file: str | Path = ".env",
    relay_root: str | Path = DEFAULT_CODEX_COORDINATION_RELAY_ROOT,
    session_root: str | Path | None = None,
    confirm: str = "",
    policy: CodexCoordinationRelayPolicy | None = None,
    postcheck_roots: list[str | Path] | None = None,
    session_fn: Callable[..., dict[str, Any]] = run_codex_coordination_session,
    time_fn=time.monotonic,
) -> dict[str, Any]:
    actual_env = dict(os.environ if env is None else env)
    actual_policy = policy or CodexCoordinationRelayPolicy.from_env(actual_env)
    started = time_fn()
    session_plan = build_codex_coordination_relay_session_plan(plan)
    relay_id = str(session_plan["session_id"])
    root = Path(relay_root)
    output: dict[str, Any] = {
        "schema": CODEX_COORDINATION_RELAY_SCHEMA,
        "ok": True,
        "dry_run": False,
        "persistent": False,
        "auto_ingest": False,
        "memory": "off",
        "relay_id": relay_id,
        "policy": actual_policy.to_record(),
        "problems": [],
    }
    gate_problems = validate_codex_coordination_relay_gate(actual_env, confirm=confirm)
    if gate_problems:
        output["ok"] = False
        output["problems"].extend(gate_problems)
        output["result"] = {"ok": False, "status": "relay_gate_failed", "problems": gate_problems}
        return _finish_relay(output, root, started, time_fn, actual_env)

    session_env = dict(actual_env)
    session_env["SYNAPS_CODEX_COORDINATION_SESSION"] = "1"
    session_env["SYNAPS_CODEX_COORDINATION_SESSION_ARMED"] = "1"
    session_payload = session_fn(
        plan=session_plan,
        env=session_env,
        env_file=env_file,
        session_root=Path(session_root) if session_root else root / relay_id / "session",
        confirm=CODEX_COORDINATION_SESSION_CONFIRM_PHRASE,
        policy=CodexCoordinationSessionPolicy(
            max_steps=actual_policy.max_steps,
            max_wall_clock_sec=actual_policy.max_wall_clock_sec,
        ),
        postcheck_roots=postcheck_roots,
    )
    output["session"] = _redacted(session_payload)
    output["ok"] = bool(session_payload.get("ok"))
    output["result"] = {
        "ok": output["ok"],
        "status": "relay_complete" if output["ok"] else "relay_failed",
        "session_status": str((session_payload.get("result") or {}).get("status") or ""),
    }
    return _finish_relay(output, root, started, time_fn, actual_env)


def _send_step(source: Mapping[str, Any], *, default_nonce: str, default_kind: str, default_note: str) -> dict[str, Any]:
    return {
        "phase": "send_file",
        "nonce": str(source.get("nonce") or default_nonce),
        "file": _required(source, "file"),
        "base_dir": _required(source, "base_dir"),
        "kind": str(source.get("kind") or default_kind),
        "note": str(source.get("note") or default_note),
        "include_payload": bool(source.get("include_payload", True)),
        "send": True,
        "max_cycles": _bounded_int(source.get("max_cycles"), 1, 1, 1),
        "sleep_sec": _bounded_float(source.get("sleep_sec"), 0.0, 0.0, 0.0),
        "max_wall_clock_sec": _bounded_float(source.get("max_wall_clock_sec"), 60.0, 1.0, 3600.0),
        "send_timeout_sec": _bounded_float(source.get("send_timeout_sec"), 10.0, 0.1, 30.0),
    }


def _wait_contract_step(source: Mapping[str, Any], *, default_nonce: str, default_note: str) -> dict[str, Any]:
    return {
        "phase": "wait_contract",
        "nonce": str(source.get("nonce") or default_nonce),
        "expect_name": _required(source, "expect_name"),
        "expect_kind": str(source.get("expect_kind") or "codex_contract"),
        "expect_sender": _required(source, "expect_sender"),
        "note_contains": str(source.get("note_contains") or default_note),
        "expect_sha256": _required_sha(source, "expect_sha256"),
        "expect_size": _required_size(source, "expect_size"),
        "apply": True,
        "max_cycles": _bounded_int(source.get("max_cycles"), 120, 1, 120),
        "sleep_sec": _bounded_float(source.get("sleep_sec"), 2.0, 0.0, 300.0),
        "max_wall_clock_sec": _bounded_float(source.get("max_wall_clock_sec"), 420.0, 1.0, 3600.0),
    }


def _wait_report_step(source: Mapping[str, Any], *, default_nonce: str, default_note: str) -> dict[str, Any]:
    return {
        "phase": "wait_report",
        "nonce": str(source.get("nonce") or default_nonce),
        "expect_name": _required(source, "expect_name"),
        "expect_name_aliases": _optional_name_aliases(source.get("expect_name_aliases")),
        "expect_kind": str(source.get("expect_kind") or "codex_report"),
        "expect_sender": _required(source, "expect_sender"),
        "note_contains": str(source.get("note_contains") or default_note),
        "expect_sha256": _required_sha(source, "expect_sha256"),
        "expect_size": _required_size(source, "expect_size"),
        "apply": True,
        "max_cycles": _bounded_int(source.get("max_cycles"), 120, 1, 120),
        "sleep_sec": _bounded_float(source.get("sleep_sec"), 2.0, 0.0, 300.0),
        "max_wall_clock_sec": _bounded_float(source.get("max_wall_clock_sec"), 420.0, 1.0, 3600.0),
    }


def _safe_relay_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("schema") not in {CODEX_COORDINATION_RELAY_PLAN_SCHEMA, None, ""}:
        raise SynapsValidationError("unsupported coordination relay plan schema")
    return dict(plan)


def _mapping(plan: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = plan.get(key)
    if not isinstance(value, Mapping):
        raise SynapsValidationError(f"relay {key} must be an object")
    return dict(value)


def _required(source: Mapping[str, Any], key: str) -> str:
    value = str(source.get(key) or "").strip()
    if not value:
        raise SynapsValidationError(f"{key} is required")
    return value


def _optional_name_aliases(raw: Any) -> list[str]:
    if raw is None or raw == "":
        return []
    if not isinstance(raw, list):
        raise SynapsValidationError("expect_name_aliases must be a list")
    aliases: list[str] = []
    for item in raw[:5]:
        alias = str(item or "").strip()
        if alias:
            aliases.append(alias)
    return aliases


def _required_sha(source: Mapping[str, Any], key: str) -> str:
    value = _required(source, key).lower()
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise SynapsValidationError(f"{key} must be sha256")
    return value


def _required_size(source: Mapping[str, Any], key: str) -> int:
    try:
        value = int(source.get(key))
    except Exception as exc:
        raise SynapsValidationError(f"{key} must be an integer") from exc
    if value < 0:
        raise SynapsValidationError(f"{key} must be non-negative")
    return value


def _finish_relay(
    payload: dict[str, Any],
    root: Path,
    started: float,
    time_fn,
    env: Mapping[str, str],
) -> dict[str, Any]:
    payload["elapsed_sec"] = round(max(0.0, float(time_fn() - started)), 3)
    redaction = _redaction_problems(payload, env)
    if redaction:
        payload["ok"] = False
        payload.setdefault("problems", []).extend(redaction)
        payload["result"] = {"ok": False, "status": "redaction_failed", "problems": redaction}
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


def _redaction_problems(payload: Mapping[str, Any], env: Mapping[str, str]) -> list[str]:
    token = str(env.get("SISTER_SYNC_TOKEN") or "")
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    problems: list[str] = []
    if "payload_b64" in text:
        problems.append("payload_b64_leaked_to_relay_output")
    if '"token"' in text or "SISTER_SYNC_TOKEN" in text or (token and token in text):
        problems.append("token_leaked_to_relay_output")
    if '"content"' in text:
        problems.append("content_leaked_to_relay_output")
    return problems


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"created_at": _utc_now(), **dict(record)}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _safe_token(raw: str, label: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(raw or "").strip()).strip("-_")
    if not safe:
        raise SynapsValidationError(f"{label} is required")
    return safe[:120]


def _env_bool(raw: str | None) -> bool:
    return str(raw or "0").strip().lower() in {"1", "true", "yes", "on", "y", "enabled"}


def _bounded_int(raw: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw if raw is not None and str(raw).strip() else default)
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _bounded_float(raw: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(raw if raw is not None and str(raw).strip() else default)
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
