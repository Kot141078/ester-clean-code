"""One-shot SYNAPS Codex coordination relay tick.

This runner selects at most one approved relay plan, runs the bounded relay
wrapper once, records a metadata-only mark, and exits. It is not a scheduler or
persistent daemon.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .codex_coordination_relay import (
    CODEX_COORDINATION_RELAY_CONFIRM_PHRASE,
    DEFAULT_CODEX_COORDINATION_RELAY_ROOT,
    CodexCoordinationRelayPolicy,
    run_codex_coordination_relay,
)
from .codex_daemon import codex_daemon_arm_status
from .protocol import SynapsValidationError


CODEX_COORDINATION_RELAY_TICK_SCHEMA = "ester.synaps.codex_coordination_relay_tick.v1"
CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_COORDINATION_RELAY_TICK_RUN"
DEFAULT_CODEX_COORDINATION_RELAY_TICK_ROOT = Path("data") / "synaps" / "codex_bridge" / "coordination_relay_tick"
DEFAULT_CODEX_COORDINATION_RELAY_PLAN_QUEUE = DEFAULT_CODEX_COORDINATION_RELAY_TICK_ROOT / "queue"
DEFAULT_CODEX_COORDINATION_RELAY_PLAN_COMPLETED = DEFAULT_CODEX_COORDINATION_RELAY_TICK_ROOT / "completed"
DEFAULT_CODEX_COORDINATION_RELAY_PLAN_FAILED = DEFAULT_CODEX_COORDINATION_RELAY_TICK_ROOT / "failed"
DEFAULT_CODEX_COORDINATION_RELAY_TICK_LEDGER = DEFAULT_CODEX_COORDINATION_RELAY_TICK_ROOT / "events.jsonl"


@dataclass(frozen=True)
class CodexCoordinationRelayTickPolicy:
    max_wall_clock_sec: float = 1200.0
    max_plan_bytes: int = 128 * 1024
    postcheck_max_file_bytes: int = 1024 * 1024

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexCoordinationRelayTickPolicy":
        source = os.environ if env is None else env
        return cls(
            max_wall_clock_sec=_bounded_float(
                source.get("SYNAPS_CODEX_COORDINATION_RELAY_TICK_MAX_WALL_CLOCK_SEC"),
                1200.0,
                1.0,
                3600.0,
            ),
            max_plan_bytes=_bounded_int(
                source.get("SYNAPS_CODEX_COORDINATION_RELAY_TICK_MAX_PLAN_BYTES"),
                128 * 1024,
                1024,
                512 * 1024,
            ),
            postcheck_max_file_bytes=_bounded_int(
                source.get("SYNAPS_CODEX_COORDINATION_RELAY_TICK_POSTCHECK_MAX_FILE_BYTES"),
                1024 * 1024,
                1024,
                5 * 1024 * 1024,
            ),
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodexCoordinationRelayPlanSelector:
    expected_name: str = ""
    expected_sha256: str = ""
    expected_size: int | None = None

    def exact(self) -> bool:
        return bool(self.expected_name and len(self.expected_sha256) == 64 and self.expected_size is not None)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def validate_codex_coordination_relay_tick_gate(env: Mapping[str, str], *, confirm: str = "") -> list[str]:
    status = codex_daemon_arm_status(env)
    problems: list[str] = []
    if confirm != CODEX_COORDINATION_RELAY_TICK_CONFIRM_PHRASE:
        problems.append("missing_codex_coordination_relay_tick_confirm_phrase")
    if not _env_bool(env.get("SYNAPS_CODEX_COORDINATION_RELAY_TICK", "0")):
        problems.append("SYNAPS_CODEX_COORDINATION_RELAY_TICK_not_enabled")
    if not _env_bool(env.get("SYNAPS_CODEX_COORDINATION_RELAY_TICK_ARMED", "0")):
        problems.append("SYNAPS_CODEX_COORDINATION_RELAY_TICK_ARMED_not_enabled")
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


def run_codex_coordination_relay_tick(
    *,
    env: Mapping[str, str] | None = None,
    env_file: str | Path = ".env",
    queue_root: str | Path = DEFAULT_CODEX_COORDINATION_RELAY_PLAN_QUEUE,
    completed_root: str | Path = DEFAULT_CODEX_COORDINATION_RELAY_PLAN_COMPLETED,
    failed_root: str | Path = DEFAULT_CODEX_COORDINATION_RELAY_PLAN_FAILED,
    ledger_path: str | Path = DEFAULT_CODEX_COORDINATION_RELAY_TICK_LEDGER,
    relay_root: str | Path = DEFAULT_CODEX_COORDINATION_RELAY_ROOT,
    session_root: str | Path | None = None,
    selector: CodexCoordinationRelayPlanSelector | None = None,
    confirm: str = "",
    policy: CodexCoordinationRelayTickPolicy | None = None,
    relay_policy: CodexCoordinationRelayPolicy | None = None,
    postcheck_roots: list[str | Path] | None = None,
    relay_fn: Callable[..., dict[str, Any]] = run_codex_coordination_relay,
    time_fn=time.monotonic,
) -> dict[str, Any]:
    actual_env = dict(os.environ if env is None else env)
    actual_policy = policy or CodexCoordinationRelayTickPolicy.from_env(actual_env)
    safe_selector = selector or CodexCoordinationRelayPlanSelector()
    started = time_fn()
    env_path = Path(env_file) if str(env_file or "") else None
    env_before = _fingerprint_optional(env_path)
    roots = _resolve_roots(queue_root, completed_root, failed_root, ledger_path, relay_root, session_root)
    output: dict[str, Any] = {
        "schema": CODEX_COORDINATION_RELAY_TICK_SCHEMA,
        "ok": True,
        "persistent": False,
        "auto_ingest": False,
        "memory": "off",
        "selector": safe_selector.to_record(),
        "policy": actual_policy.to_record(),
        "problems": [],
    }
    gate_problems = validate_codex_coordination_relay_tick_gate(actual_env, confirm=confirm)
    if gate_problems or roots["problems"]:
        output["ok"] = False
        output["problems"].extend([*gate_problems, *roots["problems"]])
        output["result"] = {"ok": False, "status": "relay_tick_gate_failed", "problems": output["problems"]}
        return _finish_tick(output, roots, started, time_fn, actual_policy, env_path, env_before, postcheck_roots, actual_env)

    candidates = _queued_plan_candidates(roots["queue_root"], roots["completed_root"], roots["failed_root"], safe_selector, actual_policy)
    output["candidate_count"] = len(candidates)
    output["candidates"] = [_candidate_record(candidate) for candidate in candidates]
    selection_problem = _selection_problem(candidates, safe_selector)
    if selection_problem:
        output["ok"] = selection_problem == "no_queued_plan"
        output["result"] = {"ok": output["ok"], "status": selection_problem}
        if not output["ok"]:
            output["problems"].append(selection_problem)
        return _finish_tick(output, roots, started, time_fn, actual_policy, env_path, env_before, postcheck_roots, actual_env)

    candidate = candidates[0]
    output["selected_plan"] = _candidate_record(candidate)
    lock_path = roots["ledger_path"].parent / "locks" / f"{candidate['safe_id']}.lock"
    lock_acquired = False
    try:
        _acquire_lock(lock_path, candidate)
        lock_acquired = True
        before = dict(candidate["fingerprint"])
        plan = _load_plan(candidate["path"], actual_policy)
        if before != _fingerprint(candidate["path"]):
            raise SynapsValidationError("relay_plan_changed_during_load")
        relay_env = dict(actual_env)
        relay_env["SYNAPS_CODEX_COORDINATION_RELAY"] = "1"
        relay_env["SYNAPS_CODEX_COORDINATION_RELAY_ARMED"] = "1"
        relay_payload = relay_fn(
            plan=plan,
            env=relay_env,
            env_file=env_file,
            relay_root=roots["relay_root"],
            session_root=roots["session_root"],
            confirm=CODEX_COORDINATION_RELAY_CONFIRM_PHRASE,
            policy=relay_policy or CodexCoordinationRelayPolicy.from_env(relay_env),
            postcheck_roots=postcheck_roots,
        )
        output["relay"] = _redacted(relay_payload)
        if before != _fingerprint(candidate["path"]):
            raise SynapsValidationError("relay_plan_changed_before_mark")
        status = "completed" if relay_payload.get("ok") else "failed"
        output["mark"] = _write_mark(
            roots["completed_root"] if status == "completed" else roots["failed_root"],
            candidate,
            status=status,
            reason=str((relay_payload.get("result") or {}).get("status") or status),
        )
        output["ok"] = bool(relay_payload.get("ok"))
        output["result"] = {"ok": output["ok"], "status": f"relay_tick_{status}", "relay_status": (relay_payload.get("result") or {}).get("status")}
    except Exception as exc:
        output["ok"] = False
        output.setdefault("problems", []).append(str(exc))
        try:
            output["mark"] = _write_mark(roots["failed_root"], candidate, status="failed", reason=str(exc))
        except Exception:
            pass
        output["result"] = {"ok": False, "status": "relay_tick_failed", "error": exc.__class__.__name__}
    finally:
        if lock_acquired:
            _release_lock(lock_path)

    return _finish_tick(output, roots, started, time_fn, actual_policy, env_path, env_before, postcheck_roots, actual_env)


def _resolve_roots(queue_root, completed_root, failed_root, ledger_path, relay_root, session_root) -> dict[str, Any]:
    problems: list[str] = []
    roots: dict[str, Any] = {"problems": problems}
    for key, raw in {
        "queue_root": queue_root,
        "completed_root": completed_root,
        "failed_root": failed_root,
        "relay_root": relay_root,
    }.items():
        try:
            roots[key] = _safe_root(raw)
        except Exception:
            problems.append(f"{key}_invalid")
    try:
        roots["session_root"] = None if session_root is None else _safe_root(session_root)
    except Exception:
        problems.append("session_root_invalid")
    try:
        roots["ledger_path"] = Path(ledger_path).resolve()
    except Exception:
        problems.append("ledger_path_invalid")
    return roots


def _queued_plan_candidates(
    queue_root: Path,
    completed_root: Path,
    failed_root: Path,
    selector: CodexCoordinationRelayPlanSelector,
    policy: CodexCoordinationRelayTickPolicy,
) -> list[dict[str, Any]]:
    if not queue_root.exists():
        return []
    candidates: list[dict[str, Any]] = []
    for path in sorted(queue_root.glob("*.json"), key=lambda item: item.name):
        try:
            resolved = path.resolve()
            resolved.relative_to(queue_root)
            if path.is_symlink():
                continue
            fingerprint = _fingerprint(resolved)
            if fingerprint["size"] > policy.max_plan_bytes:
                continue
            if selector.expected_name and path.name != selector.expected_name:
                continue
            if selector.expected_sha256 and fingerprint["sha256"] != selector.expected_sha256:
                continue
            if selector.expected_size is not None and fingerprint["size"] != selector.expected_size:
                continue
            safe_id = _safe_plan_id(path.name, fingerprint["sha256"])
            if _marked(completed_root, safe_id) or _marked(failed_root, safe_id):
                continue
            candidates.append({"path": resolved, "name": path.name, "fingerprint": fingerprint, "safe_id": safe_id})
        except Exception:
            continue
    return candidates


def _selection_problem(candidates: list[Mapping[str, Any]], selector: CodexCoordinationRelayPlanSelector) -> str:
    if not candidates:
        return "expected_exactly_one_relay_plan:0" if selector.exact() else "no_queued_plan"
    if len(candidates) > 1:
        return f"expected_exactly_one_relay_plan:{len(candidates)}"
    if selector.expected_name or selector.expected_sha256 or selector.expected_size is not None:
        if not selector.exact():
            return "exact_relay_plan_selector_required"
    return ""


def _load_plan(path: Path, policy: CodexCoordinationRelayTickPolicy) -> dict[str, Any]:
    if path.stat().st_size > policy.max_plan_bytes:
        raise SynapsValidationError("relay plan exceeds max bytes")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise SynapsValidationError("relay plan must be object")
    return dict(data)


def _write_mark(root: Path, candidate: Mapping[str, Any], *, status: str, reason: str) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{candidate['safe_id']}.json"
    record = {
        "schema": CODEX_COORDINATION_RELAY_TICK_SCHEMA,
        "event": f"relay_plan_{status}",
        "created_at": _utc_now(),
        "plan_name": candidate["name"],
        "plan_sha256": candidate["fingerprint"]["sha256"],
        "plan_size": candidate["fingerprint"]["size"],
        "status": status,
        "reason": reason[:200],
        "auto_ingest": False,
        "memory": "off",
    }
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
    return {"ok": True, "status": status, "path": str(path)}


def _finish_tick(
    payload: dict[str, Any],
    roots: Mapping[str, Any],
    started: float,
    time_fn,
    policy: CodexCoordinationRelayTickPolicy,
    env_path: Path | None,
    env_before: dict[str, Any] | None,
    postcheck_roots: list[str | Path] | None,
    env: Mapping[str, str],
) -> dict[str, Any]:
    payload["elapsed_sec"] = round(max(0.0, float(time_fn() - started)), 3)
    if payload["elapsed_sec"] > policy.max_wall_clock_sec:
        payload["ok"] = False
        payload.setdefault("problems", []).append("relay_tick_max_wall_clock_exceeded")
    env_after = _fingerprint_optional(env_path)
    payload["env_file"] = {"stable": env_before == env_after, "exists": env_after is not None}
    if env_before != env_after:
        payload["ok"] = False
        payload.setdefault("problems", []).append("env_file_changed_during_relay_tick")
    postcheck = _postcheck_marker_scan(_collect_markers(payload), postcheck_roots, policy.postcheck_max_file_bytes)
    payload["postcheck"] = postcheck
    if not postcheck["ok"]:
        payload["ok"] = False
        payload.setdefault("problems", []).extend(postcheck["problems"])
    redaction = _redaction_problems(payload, roots, env)
    if redaction:
        payload["ok"] = False
        payload.setdefault("problems", []).extend(redaction)
    ledger_path = roots.get("ledger_path")
    if isinstance(ledger_path, Path):
        _append_jsonl(ledger_path, _redacted(payload))
    return payload


def _safe_root(raw: str | Path) -> Path:
    path = Path(raw)
    if path.exists() and path.is_symlink():
        raise SynapsValidationError("root symlink rejected")
    return path.resolve()


def _marked(root: Path, safe_id: str) -> bool:
    return (root / f"{safe_id}.json").exists()


def _acquire_lock(path: Path, candidate: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"schema": CODEX_COORDINATION_RELAY_TICK_SCHEMA, "plan": candidate["name"], "created_at": _utc_now()}
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))


def _release_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _candidate_record(candidate: Mapping[str, Any]) -> dict[str, Any]:
    fp = candidate.get("fingerprint") or {}
    return {"name": candidate.get("name"), "sha256": fp.get("sha256"), "size": fp.get("size"), "mtime_ns": fp.get("mtime_ns")}


def _fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {"path": str(path.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": _sha256_file(path)}


def _fingerprint_optional(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return _fingerprint(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_plan_id(name: str, sha256: str) -> str:
    safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in name)[:80]
    return f"{safe_name}.{sha256[:12]}"


def _collect_markers(payload: Mapping[str, Any]) -> list[str]:
    selected = payload.get("selected_plan") or {}
    return [str(selected.get("name") or ""), str(selected.get("sha256") or "")]


def _postcheck_marker_scan(markers: list[str], roots: list[str | Path] | None, max_file_bytes: int) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    actual_roots = [Path(root) for root in (roots or [])]
    for root in actual_roots:
        if not root.exists():
            continue
        for file_path in root.rglob("*"):
            if not file_path.is_file() or file_path.stat().st_size > max_file_bytes:
                continue
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for marker in markers:
                if marker and marker in text:
                    hits.append({"path": str(file_path), "marker": marker[:80]})
    return {"ok": not hits, "roots": [str(root) for root in actual_roots], "hits": hits, "problems": ["postcheck_marker_found"] if hits else []}


def _redaction_problems(payload: Mapping[str, Any], roots: Mapping[str, Any], env: Mapping[str, str]) -> list[str]:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    token_value = str(env.get("SISTER_SYNC_TOKEN") or "")
    problems: list[str] = []
    if "payload_b64" in text:
        problems.append("payload_b64_leaked_to_relay_tick_output")
    if '"token"' in text or "sync_token" in text or "SISTER_SYNC_TOKEN" in text or (token_value and token_value in text):
        problems.append("token_leaked_to_relay_tick_output")
    if '"content"' in text:
        problems.append("content_leaked_to_relay_tick_output")
    for root_key in ("ledger_path", "relay_root", "session_root"):
        root = roots.get(root_key)
        if not isinstance(root, Path) or not root.exists():
            continue
        paths = [root] if root.is_file() else list(root.rglob("*"))
        for path in paths:
            if not path.is_file() or path.stat().st_size > 1024 * 1024:
                continue
            data = path.read_text(encoding="utf-8", errors="ignore")
            if "payload_b64" in data or '"token"' in data or "SISTER_SYNC_TOKEN" in data or (token_value and token_value in data):
                problems.append("forbidden_pattern_leaked_to_relay_tick_ledgers")
                return problems
    return problems


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


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"created_at": _utc_now(), **dict(record)}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


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
