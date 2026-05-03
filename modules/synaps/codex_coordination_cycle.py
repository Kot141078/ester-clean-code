"""One-shot SYNAPS Codex coordination cycle wrapper.

This module composes already-proven primitives into a bounded operator-started
cycle. It never becomes a daemon and never promotes, enqueues, or executes
received payloads.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .codex_coordination_scanner import (
    CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE,
    CODEX_COORDINATION_SCANNER_MARK_CONFIRM_PHRASE,
    DEFAULT_CODEX_COORDINATION_SCANNER_ROOT,
    CodexCoordinationScannerPolicy,
    CodexCoordinationSelector,
    scan_codex_coordination_message,
)
from .codex_daemon import DEFAULT_CODEX_DAEMON_ROOT, codex_daemon_arm_status
from .codex_report_observer import (
    CODEX_REPORT_WAITER_CONFIRM_PHRASE,
    DEFAULT_CODEX_RECEIPT_LEDGER,
    CodexReportSelector,
    CodexReportWatcherPolicy,
    wait_for_codex_report_by_manifest,
)
from .codex_request import DEFAULT_CODEX_REQUEST_ROOT
from .file_transfer import (
    DEFAULT_QUARANTINE_ROOT,
    FILE_TRANSFER_CONFIRM_PHRASE,
    FileTransferPolicy,
    build_file_manifest,
    build_file_manifest_request,
    validate_file_transfer_send_gate,
)
from .mailbox import DEFAULT_CODEX_INBOX_ROOT
from .protocol import SynapsConfig, SynapsPreparedRequest, SynapsValidationError, config_from_env


CODEX_COORDINATION_CYCLE_SCHEMA = "ester.synaps.codex_coordination_cycle.v1"
CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_COORDINATION_CYCLE_RUN"
DEFAULT_CODEX_COORDINATION_CYCLE_ROOT = Path("data") / "synaps" / "codex_bridge" / "coordination_cycles"

PHASE_SEND_FILE = "send_file"
PHASE_WAIT_CONTRACT = "wait_contract"
PHASE_WAIT_REPORT = "wait_report"
_PHASES = frozenset({PHASE_SEND_FILE, PHASE_WAIT_CONTRACT, PHASE_WAIT_REPORT})


@dataclass(frozen=True)
class CodexCoordinationCyclePolicy:
    max_cycles: int = 3
    sleep_sec: float = 5.0
    max_wall_clock_sec: float = 600.0
    require_exact_for_live_wait: bool = True
    postcheck_max_file_bytes: int = 1024 * 1024

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexCoordinationCyclePolicy":
        source = os.environ if env is None else env
        return cls(
            max_cycles=_bounded_int(source.get("SYNAPS_CODEX_COORDINATION_CYCLE_MAX_CYCLES"), 3, 1, 120),
            sleep_sec=_bounded_float(source.get("SYNAPS_CODEX_COORDINATION_CYCLE_SLEEP_SEC"), 5.0, 0.0, 300.0),
            max_wall_clock_sec=_bounded_float(
                source.get("SYNAPS_CODEX_COORDINATION_CYCLE_MAX_WALL_CLOCK_SEC"),
                600.0,
                1.0,
                3600.0,
            ),
            require_exact_for_live_wait=not _env_bool(
                source.get("SYNAPS_CODEX_COORDINATION_CYCLE_ALLOW_MISSING_HASH", "0")
            ),
            postcheck_max_file_bytes=_bounded_int(
                source.get("SYNAPS_CODEX_COORDINATION_CYCLE_POSTCHECK_MAX_FILE_BYTES"),
                1024 * 1024,
                1024,
                5 * 1024 * 1024,
            ),
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodexCoordinationSendSpec:
    file_path: str
    base_dir: str
    kind: str = "codex_contract"
    note: str = ""
    include_payload: bool = True

    def to_record(self) -> dict[str, Any]:
        return {
            "file_path": str(Path(self.file_path).name),
            "base_dir": str(Path(self.base_dir)),
            "kind": self.kind,
            "note": _preview(self.note, 160),
            "include_payload": self.include_payload,
        }


def codex_coordination_cycle_arm_status(env: Mapping[str, str]) -> dict[str, bool]:
    daemon_status = codex_daemon_arm_status(env)
    return {
        "cycle": _env_bool(env.get("SYNAPS_CODEX_COORDINATION_CYCLE", "0")),
        "armed": _env_bool(env.get("SYNAPS_CODEX_COORDINATION_CYCLE_ARMED", "0")),
        "scanner": _env_bool(env.get("SYNAPS_CODEX_COORDINATION_SCANNER", "0")),
        "scanner_armed": _env_bool(env.get("SYNAPS_CODEX_COORDINATION_SCANNER_ARMED", "0")),
        "file_transfer": _env_bool(env.get("SISTER_FILE_TRANSFER", "0")),
        "file_transfer_armed": _env_bool(env.get("SISTER_FILE_TRANSFER_ARMED", "0")),
        "conversation_window": _env_bool(env.get("SISTER_CONVERSATION_WINDOW", "0")),
        "conversation_window_armed": _env_bool(env.get("SISTER_CONVERSATION_WINDOW_ARMED", "0")),
        "operator_gate": _env_bool(env.get("SISTER_OPERATOR_GATE", "0")),
        "operator_gate_armed": _env_bool(env.get("SISTER_OPERATOR_GATE_ARMED", "0")),
        "schedule": _env_bool(env.get("SISTER_SCHEDULE", "0")),
        "schedule_armed": _env_bool(env.get("SISTER_SCHEDULE_ARMED", "0")),
        "legacy_autochat": daemon_status["legacy_autochat"],
        "daemon": daemon_status["daemon"],
        "daemon_armed": daemon_status["armed"],
        "observe_reports": daemon_status["observe_reports"],
        "observe_reports_armed": daemon_status["observe_reports_armed"],
        "promote_mailbox": daemon_status["promote_mailbox"],
        "enqueue_handoffs": daemon_status["enqueue_handoffs"],
        "runner": daemon_status["runner"],
        "runner_armed": daemon_status["runner_armed"],
        "persistent": daemon_status["persistent"],
        "persistent_armed": daemon_status["persistent_armed"],
        "kill_switch": daemon_status["kill_switch"],
    }


def validate_codex_coordination_cycle_gate(
    env: Mapping[str, str],
    *,
    phase: str,
    mutate: bool = False,
    send: bool = False,
    confirm: str = "",
    send_confirm: str = "",
) -> list[str]:
    status = codex_coordination_cycle_arm_status(env)
    problems: list[str] = []
    if phase not in _PHASES:
        problems.append("unknown_coordination_cycle_phase")
    if confirm != CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE:
        problems.append("missing_codex_coordination_cycle_confirm_phrase")
    if not status["cycle"]:
        problems.append("SYNAPS_CODEX_COORDINATION_CYCLE_not_enabled")
    if not status["armed"]:
        problems.append("SYNAPS_CODEX_COORDINATION_CYCLE_ARMED_not_enabled")
    if status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    if status["conversation_window"] or status["conversation_window_armed"]:
        problems.append("SISTER_CONVERSATION_WINDOW_must_remain_disabled")
    if status["operator_gate"] or status["operator_gate_armed"]:
        problems.append("SISTER_OPERATOR_GATE_must_remain_disabled")
    if status["schedule"] or status["schedule_armed"]:
        problems.append("SISTER_SCHEDULE_must_remain_disabled")
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
    if phase != PHASE_SEND_FILE and (status["file_transfer"] or status["file_transfer_armed"]):
        problems.append("SISTER_FILE_TRANSFER_must_remain_disabled_outside_send_phase")
    if phase == PHASE_WAIT_CONTRACT and mutate and (not status["scanner"] or not status["scanner_armed"]):
        problems.append("SYNAPS_CODEX_COORDINATION_SCANNER_must_be_enabled_for_wait_contract")
    if phase == PHASE_WAIT_REPORT and mutate and (
        not status["daemon"]
        or not status["daemon_armed"]
        or not status["observe_reports"]
        or not status["observe_reports_armed"]
    ):
        problems.append("SYNAPS_CODEX_DAEMON_OBSERVE_REPORTS_must_be_enabled_for_wait_report")
    if send:
        problems.extend(validate_file_transfer_send_gate(env, send_confirm))
    return problems


def run_codex_coordination_cycle_phase(
    *,
    phase: str,
    nonce: str,
    operator: str = "codex-coordination-cycle",
    env: Mapping[str, str] | None = None,
    env_file: str | Path = ".env",
    cycle_root: str | Path = DEFAULT_CODEX_COORDINATION_CYCLE_ROOT,
    selector: CodexCoordinationSelector | CodexReportSelector | None = None,
    send_spec: CodexCoordinationSendSpec | None = None,
    apply: bool = False,
    send: bool = False,
    confirm: str = "",
    send_confirm: str = "",
    config: SynapsConfig | None = None,
    policy: CodexCoordinationCyclePolicy | None = None,
    scanner_root: str | Path = DEFAULT_CODEX_COORDINATION_SCANNER_ROOT,
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    inbox_root: str | Path = DEFAULT_CODEX_INBOX_ROOT,
    daemon_root: str | Path = DEFAULT_CODEX_DAEMON_ROOT,
    receipt_ledger: str | Path = DEFAULT_CODEX_RECEIPT_LEDGER,
    request_root: str | Path = DEFAULT_CODEX_REQUEST_ROOT,
    postcheck_roots: list[str | Path] | None = None,
    sleep_fn=time.sleep,
    time_fn=time.monotonic,
    send_fn: Callable[[SynapsPreparedRequest], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    actual_env = dict(os.environ if env is None else env)
    actual_policy = policy or CodexCoordinationCyclePolicy.from_env(actual_env)
    safe_phase = str(phase or "").strip()
    safe_nonce = _safe_token(nonce, "nonce")
    safe_operator = _safe_token(operator, "operator")
    root = Path(cycle_root)
    env_path = Path(env_file) if str(env_file or "") else None
    env_before = _file_fingerprint(env_path)
    started = time_fn()
    mutate = bool(apply or send)
    lock_path = _cycle_lock_path(root, safe_nonce, safe_operator)
    output: dict[str, Any] = {
        "schema": CODEX_COORDINATION_CYCLE_SCHEMA,
        "ok": True,
        "phase": safe_phase,
        "nonce": safe_nonce,
        "operator": safe_operator,
        "cycle_root": str(root),
        "dry_run": not mutate,
        "confirm_required": CODEX_COORDINATION_CYCLE_CONFIRM_PHRASE,
        "policy": actual_policy.to_record(),
        "phase_results": [],
        "problems": [],
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
    }
    gate_problems = validate_codex_coordination_cycle_gate(
        actual_env,
        phase=safe_phase,
        mutate=mutate,
        send=send,
        confirm=confirm,
        send_confirm=send_confirm,
    )
    exact_problems = _exact_selector_problems(safe_phase, selector, apply=apply, policy=actual_policy)
    if gate_problems or exact_problems:
        output["ok"] = False
        output["problems"].extend([*gate_problems, *exact_problems])
        output["result"] = {"ok": False, "status": "cycle_gate_failed", "problems": output["problems"]}
        return _finish_cycle(output, started, time_fn, actual_policy, env_path, env_before, postcheck_roots)

    lock_acquired = False
    try:
        if mutate:
            _acquire_cycle_lock(lock_path, safe_nonce=safe_nonce, operator=safe_operator)
            lock_acquired = True
            output["lock"] = {"ok": True, "path": str(lock_path)}
        if safe_phase == PHASE_SEND_FILE:
            phase_result = _run_send_file_phase(
                send_spec=send_spec,
                env=actual_env,
                config=config,
                send=send,
                send_fn=send_fn,
            )
        elif safe_phase == PHASE_WAIT_CONTRACT:
            phase_result = _run_wait_contract_phase(
                selector=selector,
                env=actual_env,
                apply=apply,
                operator=safe_operator,
                scanner_root=scanner_root,
                quarantine_root=quarantine_root,
                inbox_root=inbox_root,
                policy=actual_policy,
                sleep_fn=sleep_fn,
            )
        elif safe_phase == PHASE_WAIT_REPORT:
            phase_result = _run_wait_report_phase(
                selector=selector,
                env=actual_env,
                apply=apply,
                operator=safe_operator,
                daemon_root=daemon_root,
                quarantine_root=quarantine_root,
                inbox_root=inbox_root,
                receipt_ledger=receipt_ledger,
                request_root=request_root,
                policy=actual_policy,
                sleep_fn=sleep_fn,
            )
        else:
            phase_result = {"ok": False, "status": "unknown_phase", "problems": ["unknown_coordination_cycle_phase"]}
        output["phase_results"].append(_redacted_phase_result(phase_result))
        output["ok"] = bool(phase_result.get("ok"))
        if not output["ok"]:
            output["problems"].extend(list(phase_result.get("problems") or []))
        output["result"] = {
            "ok": output["ok"],
            "status": str((phase_result.get("result") or {}).get("status") or phase_result.get("status") or "phase_complete"),
        }
    except Exception as exc:
        output["ok"] = False
        output["problems"].append(str(exc))
        output["result"] = {"ok": False, "status": "cycle_exception", "error": exc.__class__.__name__}
    finally:
        if lock_acquired:
            _release_cycle_lock(lock_path)

    return _finish_cycle(output, started, time_fn, actual_policy, env_path, env_before, postcheck_roots)


def _run_send_file_phase(
    *,
    send_spec: CodexCoordinationSendSpec | None,
    env: Mapping[str, str],
    config: SynapsConfig | None,
    send: bool,
    send_fn: Callable[[SynapsPreparedRequest], dict[str, Any]] | None,
) -> dict[str, Any]:
    if send_spec is None:
        raise SynapsValidationError("send_spec is required")
    source = _validate_under_base(send_spec.file_path, send_spec.base_dir)
    policy = FileTransferPolicy.from_env(env)
    manifest = build_file_manifest(
        [source],
        policy,
        include_payload=send_spec.include_payload,
        base_dir=send_spec.base_dir,
        kind=send_spec.kind,
        note=send_spec.note,
    )
    request = build_file_manifest_request(config or config_from_env(env), manifest)
    result: dict[str, Any] = {
        "ok": True,
        "status": "send_prepared" if not send else "send_complete",
        "dry_run": not send,
        "transfer": {
            "transfer_id": manifest["transfer_id"],
            "mode": manifest["mode"],
            "file_count": len(manifest["files"]),
            "total_bytes": manifest["total_bytes"],
            "auto_ingest": False,
            "memory": "off",
        },
        "request": {
            "url": request.url,
            "timeout_sec": request.timeout_sec,
            "headers": dict(request.headers),
        },
    }
    if send:
        sender = send_fn or _send_prepared_request
        send_result = sender(request)
        result["send_result"] = _compact_send_result(send_result)
        result["ok"] = bool(send_result.get("ok"))
        if not result["ok"]:
            result["problems"] = [str((send_result.get("body") or {}).get("error") or "send_failed")]
    return result


def _run_wait_contract_phase(
    *,
    selector: CodexCoordinationSelector | CodexReportSelector | None,
    env: Mapping[str, str],
    apply: bool,
    operator: str,
    scanner_root: str | Path,
    quarantine_root: str | Path,
    inbox_root: str | Path,
    policy: CodexCoordinationCyclePolicy,
    sleep_fn,
) -> dict[str, Any]:
    if not isinstance(selector, CodexCoordinationSelector):
        raise SynapsValidationError("coordination selector is required for wait_contract")
    scanner_policy = CodexCoordinationScannerPolicy(
        max_cycles=policy.max_cycles,
        sleep_sec=policy.sleep_sec,
        exclude_seen=True,
    )
    payload = scan_codex_coordination_message(
        selector=selector,
        env=env,
        mark_seen=apply,
        confirm=CODEX_COORDINATION_SCANNER_MARK_CONFIRM_PHRASE if apply else CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE,
        operator=operator,
        scanner_root=scanner_root,
        quarantine_root=quarantine_root,
        inbox_root=inbox_root,
        policy=scanner_policy,
        sleep_fn=sleep_fn,
    )
    if apply and payload.get("ok"):
        repeat = scan_codex_coordination_message(
            selector=selector,
            env=env,
            mark_seen=False,
            confirm=CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE,
            operator=f"{operator}-repeat",
            scanner_root=scanner_root,
            quarantine_root=quarantine_root,
            inbox_root=inbox_root,
            policy=CodexCoordinationScannerPolicy(max_cycles=1, sleep_sec=0, exclude_seen=True),
            sleep_fn=sleep_fn,
        )
        payload["repeat_check"] = _compact_repeat(repeat)
        if repeat.get("matched") or (repeat.get("cycles") or [{}])[0].get("candidate_count") != 0:
            payload["ok"] = False
            payload.setdefault("problems", []).append("repeat_check_found_candidate")
    return payload


def _run_wait_report_phase(
    *,
    selector: CodexCoordinationSelector | CodexReportSelector | None,
    env: Mapping[str, str],
    apply: bool,
    operator: str,
    daemon_root: str | Path,
    quarantine_root: str | Path,
    inbox_root: str | Path,
    receipt_ledger: str | Path,
    request_root: str | Path,
    policy: CodexCoordinationCyclePolicy,
    sleep_fn,
) -> dict[str, Any]:
    if not isinstance(selector, CodexReportSelector):
        raise SynapsValidationError("report selector is required for wait_report")
    payload = wait_for_codex_report_by_manifest(
        selector=selector,
        env=env,
        apply=apply,
        confirm=CODEX_REPORT_WAITER_CONFIRM_PHRASE if apply else "",
        operator=operator,
        daemon_root=daemon_root,
        quarantine_root=quarantine_root,
        inbox_root=inbox_root,
        receipt_ledger=receipt_ledger,
        request_root=request_root,
        watcher_policy=CodexReportWatcherPolicy(max_cycles=policy.max_cycles, sleep_sec=policy.sleep_sec),
        sleep_fn=sleep_fn,
    )
    if apply and payload.get("ok"):
        repeat = wait_for_codex_report_by_manifest(
            selector=selector,
            env=env,
            apply=False,
            confirm="",
            operator=f"{operator}-repeat",
            daemon_root=daemon_root,
            quarantine_root=quarantine_root,
            inbox_root=inbox_root,
            receipt_ledger=receipt_ledger,
            request_root=request_root,
            watcher_policy=CodexReportWatcherPolicy(max_cycles=1, sleep_sec=0),
            sleep_fn=sleep_fn,
        )
        payload["repeat_check"] = _compact_repeat(repeat)
        if repeat.get("matched") or (repeat.get("cycles") or [{}])[0].get("candidate_count") != 0:
            payload["ok"] = False
            payload.setdefault("problems", []).append("repeat_check_found_candidate")
    return payload


def _finish_cycle(
    payload: dict[str, Any],
    started: float,
    time_fn,
    policy: CodexCoordinationCyclePolicy,
    env_path: Path | None,
    env_before: dict[str, Any] | None,
    postcheck_roots: list[str | Path] | None,
) -> dict[str, Any]:
    elapsed = max(0.0, float(time_fn() - started))
    payload["elapsed_sec"] = round(elapsed, 3)
    if elapsed > policy.max_wall_clock_sec:
        payload["ok"] = False
        payload.setdefault("problems", []).append("max_wall_clock_exceeded")
    env_after = _file_fingerprint(env_path)
    payload["env_file"] = {"stable": env_before == env_after, "exists": env_after is not None}
    if env_before != env_after:
        payload["ok"] = False
        payload.setdefault("problems", []).append("env_file_changed_during_cycle")
    markers = [str(payload.get("nonce") or ""), *_collect_transfer_ids(payload)]
    postcheck = _postcheck_marker_scan(markers, postcheck_roots, policy.postcheck_max_file_bytes)
    payload["postcheck"] = postcheck
    if not postcheck["ok"]:
        payload["ok"] = False
        payload.setdefault("problems", []).extend(postcheck["problems"])
    redaction_problems = _redaction_problems(payload)
    if redaction_problems:
        payload["ok"] = False
        payload.setdefault("problems", []).extend(redaction_problems)
    _write_redacted_ledger(payload)
    payload["result"] = dict(payload.get("result") or {"status": "cycle_complete"})
    payload["result"]["ok"] = bool(payload.get("ok"))
    if not payload.get("ok") and "status" not in payload["result"]:
        payload["result"]["status"] = "cycle_failed"
    return payload


def _write_redacted_ledger(payload: Mapping[str, Any]) -> None:
    root = Path(DEFAULT_CODEX_COORDINATION_CYCLE_ROOT)
    if payload.get("phase_results"):
        root = Path(str(payload.get("cycle_root") or DEFAULT_CODEX_COORDINATION_CYCLE_ROOT))
    event = _redacted_phase_result(dict(payload))
    event["created_at"] = _utc_now()
    _append_jsonl(root / "events.jsonl", event)


def _exact_selector_problems(
    phase: str,
    selector: CodexCoordinationSelector | CodexReportSelector | None,
    *,
    apply: bool,
    policy: CodexCoordinationCyclePolicy,
) -> list[str]:
    if phase not in {PHASE_WAIT_CONTRACT, PHASE_WAIT_REPORT} or not apply or not policy.require_exact_for_live_wait:
        return []
    if selector is None:
        return ["selector_required"]
    expected_sha256 = str(getattr(selector, "expected_sha256", "") or "")
    expected_size = getattr(selector, "expected_size", None)
    problems = []
    if len(expected_sha256) != 64:
        problems.append("expected_sha256_required_for_live_wait")
    if expected_size is None:
        problems.append("expected_size_required_for_live_wait")
    return problems


def _validate_under_base(file_path: str, base_dir: str) -> Path:
    if not str(base_dir or "").strip():
        raise SynapsValidationError("base_dir is required")
    base = Path(base_dir).resolve()
    source = Path(file_path).resolve()
    try:
        source.relative_to(base)
    except ValueError as exc:
        raise SynapsValidationError("file escapes base-dir") from exc
    if not source.is_file():
        raise SynapsValidationError("file not found")
    return source


def _acquire_cycle_lock(path: Path, *, safe_nonce: str, operator: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"schema": CODEX_COORDINATION_CYCLE_SCHEMA, "nonce": safe_nonce, "operator": operator, "created_at": _utc_now()}
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
    except FileExistsError as exc:
        raise SynapsValidationError("coordination_cycle_lock_exists") from exc


def _release_cycle_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _cycle_lock_path(root: Path, nonce: str, operator: str) -> Path:
    return root / "locks" / f"{nonce}__{operator}.lock"


def _file_fingerprint(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    stat = path.stat()
    return {"mtime_ns": stat.st_mtime_ns, "size": stat.st_size}


def _postcheck_marker_scan(markers: list[str], roots: list[str | Path] | None, max_file_bytes: int) -> dict[str, Any]:
    actual_markers = [marker for marker in markers if marker]
    if not actual_markers:
        return {"ok": True, "roots": [], "problems": []}
    actual_roots = [Path(root) for root in (roots if roots is not None else [])]
    hits: list[dict[str, str]] = []
    for root in actual_roots:
        if not root.exists():
            continue
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                if file_path.stat().st_size > max_file_bytes:
                    continue
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for marker in actual_markers:
                if marker in text:
                    hits.append({"path": str(file_path), "marker": _preview(marker, 80)})
    return {
        "ok": not hits,
        "roots": [str(root) for root in actual_roots],
        "hits": hits,
        "problems": ["postcheck_marker_found"] if hits else [],
    }


def _redacted_phase_result(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"payload_b64", "token", "content"}:
                continue
            if key in {"cycles"} and isinstance(item, list):
                out[key] = [_compact_cycle(cycle) for cycle in item]
            else:
                out[key] = _redacted_phase_result(item)
        return out
    if isinstance(value, list):
        return [_redacted_phase_result(item) for item in value]
    if isinstance(value, str):
        return _preview(value, 600)
    return value


def _compact_cycle(cycle: Any) -> Any:
    if not isinstance(cycle, Mapping):
        return _redacted_phase_result(cycle)
    return {
        "cycle": cycle.get("cycle"),
        "matched": bool(cycle.get("matched")),
        "candidate_count": cycle.get("candidate_count"),
        "selected_transfer_id": cycle.get("selected_transfer_id") or "",
        "problems": list(cycle.get("problems") or []),
    }


def _compact_repeat(payload: Mapping[str, Any]) -> dict[str, Any]:
    cycles = list(payload.get("cycles") or [])
    return {
        "ok": bool(payload.get("ok")),
        "matched": bool(payload.get("matched")),
        "candidate_count": cycles[0].get("candidate_count") if cycles else 0,
        "status": str((payload.get("result") or {}).get("status") or ""),
    }


def _compact_send_result(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(result.get("ok")),
        "status": int(result.get("status") or 0),
        "body_status": str((result.get("body") or {}).get("status") or ""),
    }


def _redaction_problems(payload: Mapping[str, Any]) -> list[str]:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    problems: list[str] = []
    if "payload_b64" in text:
        problems.append("payload_b64_leaked_to_cycle_output")
    if '"token"' in text or "sync_token" in text or "SISTER_SYNC_TOKEN" in text:
        problems.append("token_leaked_to_cycle_output")
    return problems


def _collect_transfer_ids(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "transfer_id" or key == "selected_transfer_id":
                text = str(item or "")
                if text:
                    found.append(text)
            else:
                found.extend(_collect_transfer_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_collect_transfer_ids(item))
    return sorted(set(found))


def _send_prepared_request(request: SynapsPreparedRequest) -> dict[str, Any]:
    data = json.dumps(request.json).encode("utf-8")
    http_request = urllib.request.Request(request.url, data=data, headers=request.headers, method="POST")
    try:
        with urllib.request.urlopen(http_request, timeout=request.timeout_sec) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            return {"ok": 200 <= int(response.status) < 300, "status": int(response.status), "body": _parse_json_body(body)}
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        return {"ok": False, "status": int(exc.code), "body": _parse_json_body(body)}
    except Exception as exc:
        return {"ok": False, "status": 0, "body": {"error": exc.__class__.__name__}}


def _parse_json_body(body: str) -> Any:
    try:
        return json.loads(body) if body else {}
    except Exception:
        return {"text": body[:500]}


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


def _safe_token(raw: str, label: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(raw or "").strip()).strip("-_")
    if not safe:
        raise SynapsValidationError(f"{label} is required")
    return safe[:120]


def _preview(text: str, limit: int) -> str:
    compact = " ".join(str(text or "").split())
    return compact[:limit]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _env_bool(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on", "y", "enabled"}
