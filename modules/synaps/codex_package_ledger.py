"""Local package ledger builder for SYNAPS Codex handoffs."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


CODEX_PACKAGE_LEDGER_SCHEMA = "ester.synaps.codex_package_ledger.v1"
CODEX_PACKAGE_LEDGER_CONFIRM_PHRASE = "ESTER_READY_FOR_CODEX_PACKAGE_LEDGER_WRITE"
DEFAULT_CODEX_PACKAGE_LEDGER_ROOT = Path("data") / "synaps" / "codex_bridge" / "package_ledgers"


@dataclass(frozen=True)
class CodexPackageLedgerPolicy:
    max_transfer_outputs: int = 64
    max_transfer_records: int = 256

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodexPackageExpectedReport:
    name: str = ""
    note_contains: str = ""
    sender: str = ""

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def build_codex_package_ledger(
    *,
    front_id: str,
    transfer_output_paths: Sequence[str | Path],
    expected_report: CodexPackageExpectedReport | None = None,
    peer_activity_path: str | Path | None = None,
    operator: str = "codex-package-ledger",
    policy: CodexPackageLedgerPolicy | None = None,
) -> dict[str, Any]:
    actual_policy = policy or CodexPackageLedgerPolicy()
    safe_front_id = _safe_front_id(front_id)
    problems: list[str] = []
    if not safe_front_id:
        problems.append("invalid_front_id")
    if len(transfer_output_paths) > actual_policy.max_transfer_outputs:
        problems.append(f"too_many_transfer_outputs:{len(transfer_output_paths)}")

    transfer_outputs = []
    transfer_records = []
    for raw_path in transfer_output_paths[: actual_policy.max_transfer_outputs]:
        item = _load_transfer_output(Path(raw_path))
        transfer_outputs.append(item)
        transfer_records.extend(item.get("transfers") or [])
    if len(transfer_records) > actual_policy.max_transfer_records:
        problems.append(f"too_many_transfer_records:{len(transfer_records)}")
        transfer_records = transfer_records[: actual_policy.max_transfer_records]

    peer_activity = _load_peer_activity(Path(peer_activity_path)) if peer_activity_path else None
    status = _classify_package(transfer_outputs, peer_activity, problems)
    ledger = {
        "schema": CODEX_PACKAGE_LEDGER_SCHEMA,
        "ok": not problems and status != "send_failed",
        "status": status,
        "front_id": safe_front_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "operator": operator,
        "policy": actual_policy.to_record(),
        "expected_report": (expected_report or CodexPackageExpectedReport()).to_record(),
        "transfer_output_count": len(transfer_outputs),
        "transfer_record_count": len(transfer_records),
        "transfer_outputs": transfer_outputs,
        "transfers": transfer_records,
        "peer_activity": peer_activity,
        "problems": problems,
        "auto_ingest": False,
        "memory": "off",
        "persistent": False,
    }
    return ledger


def write_codex_package_ledger(
    *,
    ledger: Mapping[str, Any],
    out_json: str | Path | None = None,
    out_md: str | Path | None = None,
    ledger_root: str | Path = DEFAULT_CODEX_PACKAGE_LEDGER_ROOT,
    apply: bool = False,
    confirm: str = "",
) -> dict[str, Any]:
    problems = validate_codex_package_ledger_write_gate(apply=apply, confirm=confirm)
    output: dict[str, Any] = {
        "schema": CODEX_PACKAGE_LEDGER_SCHEMA,
        "ok": not problems,
        "dry_run": not apply,
        "confirm_required": CODEX_PACKAGE_LEDGER_CONFIRM_PHRASE,
        "front_id": ledger.get("front_id", ""),
        "ledger_status": ledger.get("status", ""),
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

    front_id = str(ledger.get("front_id") or "package")
    json_path = Path(out_json) if out_json else Path(ledger_root) / f"{front_id}.json"
    md_path = Path(out_md) if out_md else Path(ledger_root) / f"{front_id}.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(dict(ledger), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_codex_package_ledger_markdown(ledger), encoding="utf-8")
    output["paths"] = {"json": str(json_path), "markdown": str(md_path)}
    output["result"] = {"ok": True, "status": "ledger_written"}
    return output


def validate_codex_package_ledger_write_gate(*, apply: bool = False, confirm: str = "") -> list[str]:
    if apply and confirm != CODEX_PACKAGE_LEDGER_CONFIRM_PHRASE:
        return ["missing_codex_package_ledger_confirm_phrase"]
    return []


def render_codex_package_ledger_markdown(ledger: Mapping[str, Any]) -> str:
    expected = dict(ledger.get("expected_report") or {})
    peer = dict(ledger.get("peer_activity") or {})
    lines = [
        "# SYNAPS Codex Package Ledger",
        "",
        f"- front_id: `{ledger.get('front_id', '')}`",
        f"- status: `{ledger.get('status', '')}`",
        f"- ok: `{str(bool(ledger.get('ok'))).lower()}`",
        f"- transfer_output_count: `{ledger.get('transfer_output_count', 0)}`",
        f"- transfer_record_count: `{ledger.get('transfer_record_count', 0)}`",
        f"- expected_report: `{expected.get('name', '')}`",
        f"- expected_note: `{expected.get('note_contains', '')}`",
        f"- peer_activity_status: `{(peer.get('result') or {}).get('status', '') if isinstance(peer.get('result'), Mapping) else ''}`",
        "",
        "Transfers:",
    ]
    for item in ledger.get("transfers") or []:
        lines.append(f"- `{item.get('transfer_id', '')}` status `{item.get('status', '')}` bytes `{item.get('total_bytes', '')}`")
    lines.extend(["", "Safety: ledger only; no execution, no inbox enqueue, no memory ingest.", ""])
    return "\n".join(lines)


def _load_transfer_output(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    records = []
    transfers = list(payload.get("transfers") or [])
    results = list(payload.get("results") or [])
    if not transfers and isinstance(payload.get("transfer"), Mapping):
        transfers = [payload["transfer"]]
    for index, transfer in enumerate(transfers):
        result = results[index] if index < len(results) and isinstance(results[index], Mapping) else payload.get("result", {})
        records.append(
            {
                "transfer_id": str(transfer.get("transfer_id") or ""),
                "status": int(result.get("status") or 0) if isinstance(result, Mapping) else 0,
                "ok": bool(result.get("ok")) if isinstance(result, Mapping) and "ok" in result else bool(payload.get("ok")),
                "mode": str(transfer.get("mode") or ""),
                "total_bytes": int(transfer.get("total_bytes") or 0),
                "file_count": int(transfer.get("file_count") or 0),
                "memory": "off",
                "auto_ingest": False,
            }
        )
    chunked = payload.get("chunked") if isinstance(payload.get("chunked"), Mapping) else None
    return {
        "path": str(path),
        "ok": bool(payload.get("ok")),
        "dry_run": bool(payload.get("dry_run")),
        "manifest_count": int((payload.get("transfer") or {}).get("manifest_count") or len(records) or 0),
        "chunked": _compact_chunked(chunked),
        "transfers": records,
    }


def _load_peer_activity(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    return {
        "path": str(path),
        "ok": bool(payload.get("ok")),
        "matched": bool(payload.get("matched")),
        "branch": str(payload.get("branch") or ""),
        "selected_transfer_id": str(payload.get("selected_transfer_id") or ""),
        "cycle_count": int(payload.get("cycle_count") or 0),
        "result": dict(payload.get("result") or {}),
    }


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _compact_chunked(chunked: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not chunked:
        return None
    return {
        "schema": chunked.get("schema"),
        "transfer_id": chunked.get("transfer_id"),
        "source_name": chunked.get("source_name"),
        "source_sha256": chunked.get("source_sha256"),
        "source_size": chunked.get("source_size"),
        "requested_chunk_bytes": chunked.get("requested_chunk_bytes"),
        "chunk_bytes": chunked.get("chunk_bytes"),
        "chunk_count": chunked.get("chunk_count"),
        "index_size": chunked.get("index_size"),
        "auto_chunk_bytes": bool(chunked.get("auto_chunk_bytes")),
    }


def _classify_package(transfer_outputs: list[Mapping[str, Any]], peer_activity: Mapping[str, Any] | None, problems: list[str]) -> str:
    if problems:
        return "invalid"
    if any(not item.get("ok") for item in transfer_outputs):
        return "send_failed"
    if peer_activity:
        result = peer_activity.get("result") if isinstance(peer_activity.get("result"), Mapping) else {}
        status = str(result.get("status") or "")
        if status in {"expected_report_observed", "peer_status_observed"}:
            return status
        if status == "peer_silent":
            return "waiting_peer_silent"
        if status:
            return f"peer_activity_{status}"
    return "sent_waiting_report"


def _safe_front_id(front_id: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", front_id.strip())[:96]
    return value.strip("._-")
