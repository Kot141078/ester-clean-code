"""Bounded SYNAPS Codex coordination scanner.

The scanner is an explicit, one-shot primitive for waiting on expected
`codex_contract` or `codex_report` manifests. It never promotes, enqueues, or
executes anything; the optional mark-seen write is limited to scanner metadata.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .codex_daemon import codex_daemon_arm_status
from .file_transfer import DEFAULT_QUARANTINE_ROOT
from .mailbox import DEFAULT_CODEX_INBOX_ROOT, inspect_codex_mailbox_transfer
from .protocol import SynapsValidationError


CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_COORDINATION_SCAN"
CODEX_COORDINATION_SCANNER_MARK_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_COORDINATION_MARK_SEEN"
CODEX_COORDINATION_SCANNER_SCHEMA = "ester.synaps.codex_coordination_scanner.v1"
DEFAULT_CODEX_COORDINATION_SCANNER_ROOT = Path("data") / "synaps" / "codex_bridge" / "coordination_scanner"
_ALLOWED_COORDINATION_KINDS = frozenset({"codex_contract", "codex_report"})


@dataclass(frozen=True)
class CodexCoordinationSelector:
    expected_name: str
    expected_kind: str = ""
    expected_sender: str = ""
    note_contains: str = ""
    expected_sha256: str = ""
    expected_size: int | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodexCoordinationScannerPolicy:
    max_cycles: int = 3
    sleep_sec: float = 5.0
    exclude_seen: bool = True

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CodexCoordinationScannerPolicy":
        source = os.environ if env is None else env
        return cls(
            max_cycles=_bounded_int(source.get("SYNAPS_CODEX_COORDINATION_SCAN_MAX_CYCLES"), 3, 1, 120),
            sleep_sec=_bounded_float(source.get("SYNAPS_CODEX_COORDINATION_SCAN_SLEEP_SEC"), 5.0, 0.0, 300.0),
            exclude_seen=not _env_bool(source.get("SYNAPS_CODEX_COORDINATION_SCAN_INCLUDE_SEEN", "0")),
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def validate_codex_coordination_scanner_gate(
    env: Mapping[str, str],
    *,
    mark_seen: bool = False,
    confirm: str = "",
) -> list[str]:
    daemon_status = codex_daemon_arm_status(env)
    problems: list[str] = []
    if confirm != (CODEX_COORDINATION_SCANNER_MARK_CONFIRM_PHRASE if mark_seen else CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE):
        problems.append("missing_codex_coordination_scanner_confirm_phrase")
    if not _env_bool(env.get("SYNAPS_CODEX_COORDINATION_SCANNER", "0")):
        problems.append("SYNAPS_CODEX_COORDINATION_SCANNER_not_enabled")
    if not _env_bool(env.get("SYNAPS_CODEX_COORDINATION_SCANNER_ARMED", "0")):
        problems.append("SYNAPS_CODEX_COORDINATION_SCANNER_ARMED_not_enabled")
    if daemon_status["legacy_autochat"]:
        problems.append("SISTER_AUTOCHAT_must_remain_disabled")
    if daemon_status["persistent"] or daemon_status["persistent_armed"]:
        problems.append("SYNAPS_CODEX_DAEMON_PERSISTENT_must_remain_disabled")
    if daemon_status["runner"] or daemon_status["runner_armed"]:
        problems.append("SYNAPS_CODEX_DAEMON_RUNNER_must_remain_disabled")
    if daemon_status["promote_mailbox"]:
        problems.append("SYNAPS_CODEX_DAEMON_PROMOTE_MAILBOX_must_remain_disabled")
    if daemon_status["enqueue_handoffs"]:
        problems.append("SYNAPS_CODEX_DAEMON_ENQUEUE_HANDOFFS_must_remain_disabled")
    if daemon_status["kill_switch"]:
        problems.append("SYNAPS_CODEX_DAEMON_KILL_SWITCH_enabled")
    return problems


def scan_codex_coordination_message(
    *,
    selector: CodexCoordinationSelector,
    env: Mapping[str, str] | None = None,
    mark_seen: bool = False,
    confirm: str = "",
    operator: str = "codex-coordination-scanner",
    scanner_root: str | Path = DEFAULT_CODEX_COORDINATION_SCANNER_ROOT,
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    inbox_root: str | Path = DEFAULT_CODEX_INBOX_ROOT,
    policy: CodexCoordinationScannerPolicy | None = None,
    sleep_fn=time.sleep,
) -> dict[str, Any]:
    actual_env = os.environ if env is None else env
    safe_selector = _safe_selector(selector)
    actual_policy = policy or CodexCoordinationScannerPolicy.from_env(actual_env)
    root = Path(scanner_root)
    gate_problems = validate_codex_coordination_scanner_gate(actual_env, mark_seen=mark_seen, confirm=confirm)
    output: dict[str, Any] = {
        "schema": CODEX_COORDINATION_SCANNER_SCHEMA,
        "ok": not gate_problems,
        "dry_run": not mark_seen,
        "mark_seen": mark_seen,
        "confirm_required": CODEX_COORDINATION_SCANNER_MARK_CONFIRM_PHRASE if mark_seen else CODEX_COORDINATION_SCANNER_CONFIRM_PHRASE,
        "selector": safe_selector.to_record(),
        "policy": actual_policy.to_record(),
        "cycles": [],
        "problems": list(gate_problems),
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
    }
    if gate_problems:
        output["result"] = {"ok": False, "status": "gate_failed", "problems": gate_problems}
        return _finish_scan(output)

    for index in range(actual_policy.max_cycles):
        candidates = _coordination_candidates(
            safe_selector,
            scanner_root=root,
            quarantine_root=quarantine_root,
            inbox_root=inbox_root,
            exclude_seen=actual_policy.exclude_seen,
        )
        problems = _candidate_count_problems(candidates)
        cycle = {
            "cycle": index + 1,
            "matched": len(candidates) == 1,
            "candidate_count": len(candidates),
            "selected_transfer_id": candidates[0]["transfer_id"] if len(candidates) == 1 else "",
            "candidates": candidates,
            "problems": problems,
        }
        output["cycles"].append(cycle)
        if len(candidates) == 1:
            selected_transfer_id = str(candidates[0]["transfer_id"])
            output["matched"] = True
            output["selected_transfer_id"] = selected_transfer_id
            if not mark_seen:
                output["result"] = {"ok": True, "status": "would_select"}
                return _finish_scan(output)
            fresh_candidates = _coordination_candidates(
                safe_selector,
                scanner_root=root,
                quarantine_root=quarantine_root,
                inbox_root=inbox_root,
                exclude_seen=actual_policy.exclude_seen,
            )
            fresh_problems = _candidate_count_problems(fresh_candidates)
            cycle["pre_mark"] = {"candidate_count": len(fresh_candidates), "problems": fresh_problems}
            if fresh_problems or str(fresh_candidates[0].get("transfer_id") or "") != selected_transfer_id:
                problems = fresh_problems or ["selected_transfer_changed"]
                output["ok"] = False
                output["problems"].extend(problems)
                output["result"] = {"ok": False, "status": "pre_mark_selector_mismatch", "problems": problems}
                return _finish_scan(output)
            mark = _mark_scanner_seen(root, selected_transfer_id, operator=operator, result={"ok": True, "status": "scanner_seen"})
            cycle["mark"] = mark
            output["ok"] = True
            output["result"] = {"ok": True, "status": "scanner_seen", "marker": mark["path"]}
            return _finish_scan(output)
        if len(candidates) > 1:
            output["matched"] = False
            output["ok"] = False
            output["problems"].extend(problems)
            output["result"] = {"ok": False, "status": "selector_mismatch", "problems": problems}
            return _finish_scan(output)
        if index + 1 < actual_policy.max_cycles and actual_policy.sleep_sec:
            sleep_fn(actual_policy.sleep_sec)

    output["matched"] = False
    output["result"] = {"ok": not mark_seen, "status": "not_found", "cycles": actual_policy.max_cycles}
    output["ok"] = not mark_seen
    return _finish_scan(output)


def _coordination_candidates(
    selector: CodexCoordinationSelector,
    *,
    scanner_root: Path,
    quarantine_root: str | Path,
    inbox_root: str | Path,
    exclude_seen: bool,
) -> list[dict[str, Any]]:
    root = Path(quarantine_root)
    candidates: list[dict[str, Any]] = []
    if not root.exists():
        return candidates
    for item in sorted(root.iterdir(), key=lambda entry: entry.name):
        if not item.is_dir():
            continue
        transfer_id = item.name
        if exclude_seen and _scanner_seen_path(scanner_root, transfer_id).exists():
            continue
        try:
            inspection = inspect_codex_mailbox_transfer(transfer_id, root, inbox_root)
        except Exception:
            continue
        if not inspection.get("ok") or inspection.get("status") not in {"ready", "already_promoted"}:
            continue
        manifest = inspection.get("manifest") or {}
        if manifest.get("memory") != "off" or manifest.get("auto_ingest") is not False:
            continue
        if selector.expected_sender and str(manifest.get("received_from") or "") != selector.expected_sender:
            continue
        if selector.note_contains and selector.note_contains not in str(manifest.get("note") or ""):
            continue
        matching_files = [record for record in inspection.get("files") or [] if _selector_file_matches(selector, record)]
        if len(matching_files) != 1:
            continue
        file_record = matching_files[0]
        candidates.append(
            {
                "transfer_id": transfer_id,
                "file_name": file_record.get("name"),
                "kind": file_record.get("kind"),
                "sha256": file_record.get("sha256"),
                "size": file_record.get("size"),
                "received_from": manifest.get("received_from"),
                "note": manifest.get("note"),
                "auto_ingest": False,
                "memory": "off",
            }
        )
    return candidates


def _selector_file_matches(selector: CodexCoordinationSelector, item: Mapping[str, Any]) -> bool:
    kind = str(item.get("kind") or "")
    if selector.expected_kind and kind != selector.expected_kind:
        return False
    if not selector.expected_kind and kind not in _ALLOWED_COORDINATION_KINDS:
        return False
    if str(item.get("name") or "") != selector.expected_name:
        return False
    if selector.expected_sha256 and str(item.get("sha256") or "").lower() != selector.expected_sha256:
        return False
    if selector.expected_size is not None and int(item.get("size") or -1) != selector.expected_size:
        return False
    return bool(item.get("ok"))


def _candidate_count_problems(candidates: list[Mapping[str, Any]]) -> list[str]:
    if len(candidates) not in {0, 1}:
        return [f"expected_zero_or_one_coordination_candidate:{len(candidates)}"]
    return []


def _mark_scanner_seen(root: Path, transfer_id: str, *, operator: str, result: Mapping[str, Any]) -> dict[str, Any]:
    path = _scanner_seen_path(root, transfer_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": CODEX_COORDINATION_SCANNER_SCHEMA,
        "event": "scanner_seen",
        "created_at": _utc_now(),
        "transfer_id": _safe_transfer_id(transfer_id),
        "operator": _preview(operator, 120),
        "result": dict(result),
        "auto_ingest": False,
        "memory": "off",
    }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    event = dict(record)
    event["path"] = str(path)
    _append_jsonl(root / "events.jsonl", event)
    return {"ok": True, "status": "scanner_seen", "path": str(path)}


def _scanner_seen_path(root: Path, transfer_id: str) -> Path:
    return root / "seen" / f"{_safe_transfer_id(transfer_id)}.json"


def _finish_scan(payload: dict[str, Any]) -> dict[str, Any]:
    payload["cycle_count"] = len(payload.get("cycles") or [])
    return payload


def _safe_selector(selector: CodexCoordinationSelector) -> CodexCoordinationSelector:
    expected_name = str(selector.expected_name or "").strip()
    if not expected_name or Path(expected_name).name != expected_name:
        raise SynapsValidationError("expected coordination filename is required")
    expected_kind = str(selector.expected_kind or "").strip()
    if expected_kind and expected_kind not in _ALLOWED_COORDINATION_KINDS:
        raise SynapsValidationError("expected coordination kind must be codex_contract or codex_report")
    return CodexCoordinationSelector(
        expected_name=expected_name[:240],
        expected_kind=expected_kind,
        expected_sender=str(selector.expected_sender or "").strip()[:120],
        note_contains=str(selector.note_contains or "").strip()[:240],
        expected_sha256=str(selector.expected_sha256 or "").strip().lower()[:64],
        expected_size=selector.expected_size if selector.expected_size is None else max(0, int(selector.expected_size)),
    )


def _safe_transfer_id(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(raw or "").strip()).strip("-_")
    if not safe:
        raise SynapsValidationError("transfer id is required")
    return safe[:120]


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


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
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}
