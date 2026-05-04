"""Read-only dashboard for open SYNAPS Codex package gates."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .codex_package_ledger import DEFAULT_CODEX_PACKAGE_LEDGER_ROOT


CODEX_GATE_DASHBOARD_SCHEMA = "ester.synaps.codex_gate_dashboard.v1"
CODEX_GATE_DASHBOARD_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_GATE_DASHBOARD_WRITE"


@dataclass(frozen=True)
class CodexGateDashboardPolicy:
    max_ledgers: int = 128

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def build_codex_gate_dashboard(
    *,
    ledger_paths: Sequence[str | Path] = (),
    ledger_root: str | Path = DEFAULT_CODEX_PACKAGE_LEDGER_ROOT,
    include_root: bool = False,
    policy: CodexGateDashboardPolicy | None = None,
) -> dict[str, Any]:
    actual_policy = policy or CodexGateDashboardPolicy()
    paths = _collect_ledger_paths(ledger_paths=ledger_paths, ledger_root=ledger_root, include_root=include_root)
    problems: list[str] = []
    if len(paths) > actual_policy.max_ledgers:
        problems.append(f"too_many_ledgers:{len(paths)}")
        paths = paths[: actual_policy.max_ledgers]

    fronts = [_summarize_ledger(path) for path in paths]
    counts = Counter(str(item.get("status") or "unknown") for item in fronts)
    open_fronts = [item for item in fronts if str(item.get("status") or "").startswith("waiting") or item.get("status") in {"sent_waiting_report"}]
    payload = {
        "schema": CODEX_GATE_DASHBOARD_SCHEMA,
        "ok": not problems,
        "policy": actual_policy.to_record(),
        "ledger_count": len(fronts),
        "open_count": len(open_fronts),
        "status_counts": dict(sorted(counts.items())),
        "fronts": fronts,
        "problems": problems,
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
    }
    return payload


def write_codex_gate_dashboard(
    *,
    dashboard: Mapping[str, Any],
    out_json: str | Path | None = None,
    out_md: str | Path | None = None,
    apply: bool = False,
    confirm: str = "",
) -> dict[str, Any]:
    problems = validate_codex_gate_dashboard_write_gate(apply=apply, confirm=confirm)
    output: dict[str, Any] = {
        "schema": CODEX_GATE_DASHBOARD_SCHEMA,
        "ok": not problems,
        "dry_run": not apply,
        "confirm_required": CODEX_GATE_DASHBOARD_CONFIRM_PHRASE,
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
        json_path.write_text(json.dumps(dict(dashboard), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths["json"] = str(json_path)
    if out_md:
        md_path = Path(out_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_codex_gate_dashboard_markdown(dashboard), encoding="utf-8")
        paths["markdown"] = str(md_path)
    output["paths"] = paths
    output["result"] = {"ok": True, "status": "dashboard_written"}
    return output


def validate_codex_gate_dashboard_write_gate(*, apply: bool = False, confirm: str = "") -> list[str]:
    if apply and confirm != CODEX_GATE_DASHBOARD_CONFIRM_PHRASE:
        return ["missing_codex_gate_dashboard_confirm_phrase"]
    return []


def render_codex_gate_dashboard_markdown(dashboard: Mapping[str, Any]) -> str:
    lines = [
        "# SYNAPS Codex Open Gate Dashboard",
        "",
        f"- ok: `{str(bool(dashboard.get('ok'))).lower()}`",
        f"- ledger_count: `{dashboard.get('ledger_count', 0)}`",
        f"- open_count: `{dashboard.get('open_count', 0)}`",
        "",
        "| front | status | expected report | peer status | transfers |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in dashboard.get("fronts") or []:
        lines.append(
            "| {front} | {status} | {expected} | {peer} | {transfers} |".format(
                front=item.get("front_id", ""),
                status=item.get("status", ""),
                expected=item.get("expected_report_name", ""),
                peer=item.get("peer_activity_status", ""),
                transfers=item.get("transfer_record_count", 0),
            )
        )
    lines.extend(["", "Safety: read-only dashboard; no sends, no execution, no memory ingest.", ""])
    return "\n".join(lines)


def _collect_ledger_paths(*, ledger_paths: Sequence[str | Path], ledger_root: str | Path, include_root: bool) -> list[Path]:
    paths = [Path(item) for item in ledger_paths]
    if include_root:
        root = Path(ledger_root)
        if root.exists():
            paths.extend(sorted(root.glob("*.json")))
    unique: dict[str, Path] = {}
    for path in paths:
        unique[str(path.resolve())] = path
    return list(unique.values())


def _summarize_ledger(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = payload.get("expected_report") if isinstance(payload.get("expected_report"), Mapping) else {}
    peer = payload.get("peer_activity") if isinstance(payload.get("peer_activity"), Mapping) else {}
    peer_result = peer.get("result") if isinstance(peer.get("result"), Mapping) else {}
    return {
        "path": str(path),
        "front_id": str(payload.get("front_id") or ""),
        "ok": bool(payload.get("ok")),
        "status": str(payload.get("status") or ""),
        "expected_report_name": str(expected.get("name") or ""),
        "expected_report_note": str(expected.get("note_contains") or ""),
        "peer_activity_status": str(peer_result.get("status") or ""),
        "peer_matched": bool(peer.get("matched")),
        "transfer_record_count": int(payload.get("transfer_record_count") or 0),
        "transfer_output_count": int(payload.get("transfer_output_count") or 0),
    }
