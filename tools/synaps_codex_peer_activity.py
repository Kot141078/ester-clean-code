#!/usr/bin/env python3
"""Run one bounded SYNAPS Codex peer activity detector."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Mapping, MutableMapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_env_file(path: str | Path) -> dict[str, str]:
    if not path:
        return {}
    env_path = Path(path)
    if not env_path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip():
            values[key.strip()] = _strip_env_value(value)
    return values


def bootstrap_env_from_argv(argv: list[str], environ: MutableMapping[str, str] | None = None) -> None:
    target = os.environ if environ is None else environ
    for key, value in load_env_file(_env_file_from_argv(argv)).items():
        target.setdefault(key, value)


def merged_env(env_file: str | None = ".env", base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    if env_file:
        for key, value in load_env_file(env_file).items():
            env.setdefault(key, value)
    return env


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    bootstrap_env_from_argv(raw_argv)

    from modules.synaps import (
        CODEX_PEER_ACTIVITY_CONFIRM_PHRASE,
        CodexPeerActivityPolicy,
        CodexPeerActivitySelectors,
        CodexReportSelector,
        watch_codex_peer_activity,
    )

    parser = argparse.ArgumentParser(description="Classify one peer Codex handoff as report, status, ambiguity, or silence.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--daemon-root", default="data/synaps/codex_bridge/daemon")
    parser.add_argument("--quarantine-root", default="data/synaps/quarantine")
    parser.add_argument("--inbox-root", default="data/synaps/codex_bridge/inbox")
    parser.add_argument("--receipt-ledger", default="data/synaps/codex_bridge/receipts/events.jsonl")
    parser.add_argument("--request-root", default="data/synaps/codex_bridge/requests")
    parser.add_argument("--expect-report-name", required=True)
    parser.add_argument("--expect-report-name-alias", action="append", default=[])
    parser.add_argument("--expect-report-sender", default="")
    parser.add_argument("--expect-report-note-contains", default="")
    parser.add_argument("--expect-report-sha256", default="")
    parser.add_argument("--expect-report-size", type=int, default=-1)
    parser.add_argument("--status-name", default="")
    parser.add_argument("--status-name-alias", action="append", default=[])
    parser.add_argument("--status-sender", default="")
    parser.add_argument("--status-note-contains", default="")
    parser.add_argument("--status-sha256", default="")
    parser.add_argument("--status-size", type=int, default=-1)
    parser.add_argument("--max-cycles", type=int, default=3)
    parser.add_argument("--sleep-sec", type=float, default=5.0)
    parser.add_argument("--operator", default="codex-peer-activity")
    parser.add_argument("--status-out", default="", help="Optional markdown status artifact path.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="", help=f"Required for --apply: {CODEX_PEER_ACTIVITY_CONFIRM_PHRASE}")
    args = parser.parse_args(raw_argv)

    selectors = CodexPeerActivitySelectors(
        expected_report=CodexReportSelector(
            expected_name=args.expect_report_name,
            expected_sender=args.expect_report_sender,
            note_contains=args.expect_report_note_contains,
            expected_sha256=args.expect_report_sha256,
            expected_size=None if args.expect_report_size < 0 else args.expect_report_size,
            expected_name_aliases=tuple(args.expect_report_name_alias),
        ),
        status_report=(
            CodexReportSelector(
                expected_name=args.status_name,
                expected_sender=args.status_sender,
                note_contains=args.status_note_contains,
                expected_sha256=args.status_sha256,
                expected_size=None if args.status_size < 0 else args.status_size,
                expected_name_aliases=tuple(args.status_name_alias),
            )
            if args.status_name
            else None
        ),
    )
    payload = watch_codex_peer_activity(
        selectors=selectors,
        env=merged_env(args.env_file),
        apply=args.apply,
        confirm=args.confirm,
        operator=args.operator,
        daemon_root=args.daemon_root,
        quarantine_root=args.quarantine_root,
        inbox_root=args.inbox_root,
        receipt_ledger=args.receipt_ledger,
        request_root=args.request_root,
        policy=CodexPeerActivityPolicy(max_cycles=args.max_cycles, sleep_sec=args.sleep_sec),
    )
    if args.status_out:
        _write_status_artifact(Path(args.status_out), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


def _write_status_artifact(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = dict(payload.get("result") or {}) if isinstance(payload.get("result"), Mapping) else {}
    lines = [
        "# SYNAPS Codex Peer Activity Status",
        "",
        f"- schema: `{payload.get('schema', '')}`",
        f"- ok: `{str(bool(payload.get('ok'))).lower()}`",
        f"- dry_run: `{str(bool(payload.get('dry_run'))).lower()}`",
        f"- matched: `{str(bool(payload.get('matched'))).lower()}`",
        f"- branch: `{payload.get('branch', '')}`",
        f"- selected_transfer_id: `{payload.get('selected_transfer_id', '')}`",
        f"- status: `{result.get('status', '')}`",
        f"- cycle_count: `{payload.get('cycle_count', 0)}`",
        "",
        "Safety: no inbox promotion, no request enqueue, no execution, no memory ingest.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _strip_env_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def _env_file_from_argv(argv: list[str]) -> str:
    for index, item in enumerate(argv):
        if item == "--env-file" and index + 1 < len(argv):
            return argv[index + 1]
        if item.startswith("--env-file="):
            return item.split("=", 1)[1]
    return ".env"


if __name__ == "__main__":
    raise SystemExit(main())
