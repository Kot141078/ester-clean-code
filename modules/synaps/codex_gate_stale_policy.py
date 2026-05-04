"""Read-only stale policy for open SYNAPS Codex gates."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


CODEX_GATE_STALE_POLICY_SCHEMA = "ester.synaps.codex_gate_stale_policy.v1"
CODEX_GATE_STALE_POLICY_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_GATE_STALE_POLICY_WRITE"


@dataclass(frozen=True)
class CodexGateStalePolicy:
    max_peer_silent_open: int = 3
    stale_after_hours: float = 6.0

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_codex_gate_stale_policy(
    *,
    dashboard: Mapping[str, Any],
    policy: CodexGateStalePolicy | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    actual_policy = policy or CodexGateStalePolicy()
    actual_now = now or datetime.now(timezone.utc)
    fronts = [_summarize_front(front, now=actual_now) for front in dashboard.get("fronts") or []]
    open_fronts = [front for front in fronts if _is_open_status(str(front.get("status") or ""))]
    peer_silent = [front for front in open_fronts if front.get("status") == "waiting_peer_silent"]
    stale_fronts = [
        front
        for front in open_fronts
        if front.get("age_hours") is not None and float(front["age_hours"]) >= actual_policy.stale_after_hours
    ]
    recommendation, reason = _recommendation(
        open_count=len(open_fronts),
        peer_silent_count=len(peer_silent),
        stale_count=len(stale_fronts),
        policy=actual_policy,
    )
    output = {
        "schema": CODEX_GATE_STALE_POLICY_SCHEMA,
        "ok": True,
        "recommendation": recommendation,
        "reason": reason,
        "policy": actual_policy.to_record(),
        "dashboard_schema": dashboard.get("schema", ""),
        "dashboard_open_count": int(dashboard.get("open_count") or len(open_fronts)),
        "open_count": len(open_fronts),
        "peer_silent_count": len(peer_silent),
        "stale_count": len(stale_fronts),
        "fronts": fronts,
        "blocked_actions": _blocked_actions(recommendation),
        "allowed_actions": _allowed_actions(recommendation),
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
    }
    return output


def evaluate_codex_gate_stale_policy_file(
    *,
    dashboard_path: str | Path,
    policy: CodexGateStalePolicy | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    dashboard = json.loads(Path(dashboard_path).read_text(encoding="utf-8"))
    if not isinstance(dashboard, Mapping):
        raise ValueError("dashboard JSON must be an object")
    payload = evaluate_codex_gate_stale_policy(dashboard=dashboard, policy=policy, now=now)
    payload["dashboard_path"] = str(dashboard_path)
    return payload


def write_codex_gate_stale_policy(
    *,
    evaluation: Mapping[str, Any],
    out_json: str | Path | None = None,
    out_md: str | Path | None = None,
    apply: bool = False,
    confirm: str = "",
) -> dict[str, Any]:
    problems = validate_codex_gate_stale_policy_write_gate(apply=apply, confirm=confirm)
    output: dict[str, Any] = {
        "schema": CODEX_GATE_STALE_POLICY_SCHEMA,
        "ok": not problems,
        "dry_run": not apply,
        "confirm_required": CODEX_GATE_STALE_POLICY_CONFIRM_PHRASE,
        "problems": list(problems),
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
    }
    if problems:
        output["result"] = {"ok": False, "status": "gate_failed", "problems": problems}
        return output
    if not apply:
        output["result"] = {"ok": True, "status": "would_write"}
        return output
    if not out_json and not out_md:
        output["ok"] = False
        output["problems"].append("missing_output_path")
        output["result"] = {"ok": False, "status": "missing_output_path", "problems": ["missing_output_path"]}
        return output
    paths: dict[str, str] = {}
    if out_json:
        json_path = Path(out_json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(dict(evaluation), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths["json"] = str(json_path)
    if out_md:
        md_path = Path(out_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_codex_gate_stale_policy_markdown(evaluation), encoding="utf-8")
        paths["markdown"] = str(md_path)
    output["paths"] = paths
    output["result"] = {"ok": True, "status": "stale_policy_written"}
    return output


def validate_codex_gate_stale_policy_write_gate(*, apply: bool = False, confirm: str = "") -> list[str]:
    if apply and confirm != CODEX_GATE_STALE_POLICY_CONFIRM_PHRASE:
        return ["missing_codex_gate_stale_policy_confirm_phrase"]
    return []


def render_codex_gate_stale_policy_markdown(evaluation: Mapping[str, Any]) -> str:
    lines = [
        "# SYNAPS Codex Gate Stale Policy",
        "",
        f"- recommendation: `{evaluation.get('recommendation', '')}`",
        f"- reason: `{evaluation.get('reason', '')}`",
        f"- open_count: `{evaluation.get('open_count', 0)}`",
        f"- peer_silent_count: `{evaluation.get('peer_silent_count', 0)}`",
        f"- stale_count: `{evaluation.get('stale_count', 0)}`",
        "",
        "Allowed actions:",
    ]
    for action in evaluation.get("allowed_actions") or []:
        lines.append(f"- `{action}`")
    lines.append("")
    lines.append("Blocked actions:")
    for action in evaluation.get("blocked_actions") or []:
        lines.append(f"- `{action}`")
    lines.extend(["", "| front | status | age_hours | expected report |", "| --- | --- | --- | --- |"])
    for front in evaluation.get("fronts") or []:
        lines.append(
            "| {front} | {status} | {age} | {report} |".format(
                front=front.get("front_id", ""),
                status=front.get("status", ""),
                age=front.get("age_hours", ""),
                report=front.get("expected_report_name", ""),
            )
        )
    lines.extend(["", "Safety: policy only; no sends, no execution, no memory ingest.", ""])
    return "\n".join(lines)


def _summarize_front(front: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
    created_at = _front_created_at(front)
    age_hours = None
    if created_at:
        age_hours = round(max(0.0, (now - created_at).total_seconds() / 3600.0), 3)
    return {
        "front_id": str(front.get("front_id") or ""),
        "status": str(front.get("status") or ""),
        "expected_report_name": str(front.get("expected_report_name") or ""),
        "peer_activity_status": str(front.get("peer_activity_status") or ""),
        "path": str(front.get("path") or ""),
        "created_at": created_at.isoformat() if created_at else "",
        "age_hours": age_hours,
    }


def _front_created_at(front: Mapping[str, Any]) -> datetime | None:
    path = Path(str(front.get("path") or ""))
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw = str(payload.get("created_at") or "")
            if raw:
                return _parse_datetime(raw)
        except Exception:
            return None
    return None


def _parse_datetime(raw: str) -> datetime | None:
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _recommendation(*, open_count: int, peer_silent_count: int, stale_count: int, policy: CodexGateStalePolicy) -> tuple[str, str]:
    if peer_silent_count >= policy.max_peer_silent_open:
        return "pause_new_patch_sends", f"peer_silent_count:{peer_silent_count}>=max:{policy.max_peer_silent_open}"
    if stale_count:
        return "request_status_only", f"stale_count:{stale_count}"
    if open_count:
        return "wait", f"open_count:{open_count}"
    return "clear", "no_open_gates"


def _is_open_status(status: str) -> bool:
    return status.startswith("waiting") or status == "sent_waiting_report"


def _blocked_actions(recommendation: str) -> list[str]:
    common = ["persistent_daemon", "real_codex_worker", "scheduler_hourly", "autochat", "memory_ingest"]
    if recommendation == "pause_new_patch_sends":
        return ["new_patch_send", "new_code_front_to_peer", *common]
    if recommendation == "request_status_only":
        return ["new_patch_send", *common]
    return common


def _allowed_actions(recommendation: str) -> list[str]:
    if recommendation == "pause_new_patch_sends":
        return ["wait", "local_read_only_dashboard", "single_status_request_only"]
    if recommendation == "request_status_only":
        return ["wait", "single_status_request_only", "local_read_only_dashboard"]
    if recommendation == "clear":
        return ["local_read_only_dashboard", "next_bounded_front"]
    return ["wait", "local_read_only_dashboard"]
