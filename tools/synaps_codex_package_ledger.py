#!/usr/bin/env python3
"""Build a local SYNAPS Codex package ledger from saved transfer outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    from modules.synaps import (
        CODEX_PACKAGE_LEDGER_CONFIRM_PHRASE,
        CodexPackageExpectedReport,
        CodexPackageLedgerPolicy,
        build_codex_package_ledger,
        write_codex_package_ledger,
    )

    parser = argparse.ArgumentParser(description="Summarize one SYNAPS Codex package send into a local ledger.")
    parser.add_argument("--front-id", required=True)
    parser.add_argument("--transfer-output", action="append", default=[], help="Saved synaps_file_transfer JSON output. Repeatable.")
    parser.add_argument("--expected-report-name", default="")
    parser.add_argument("--expected-report-note-contains", default="")
    parser.add_argument("--expected-report-sender", default="")
    parser.add_argument("--peer-activity", default="", help="Optional saved synaps_codex_peer_activity JSON output.")
    parser.add_argument("--ledger-root", default="data/synaps/codex_bridge/package_ledgers")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--max-transfer-outputs", type=int, default=64)
    parser.add_argument("--max-transfer-records", type=int, default=256)
    parser.add_argument("--operator", default="codex-package-ledger")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--confirm", default="", help=f"Required for --write: {CODEX_PACKAGE_LEDGER_CONFIRM_PHRASE}")
    args = parser.parse_args(argv)

    ledger = build_codex_package_ledger(
        front_id=args.front_id,
        transfer_output_paths=args.transfer_output,
        expected_report=CodexPackageExpectedReport(
            name=args.expected_report_name,
            note_contains=args.expected_report_note_contains,
            sender=args.expected_report_sender,
        ),
        peer_activity_path=args.peer_activity or None,
        operator=args.operator,
        policy=CodexPackageLedgerPolicy(
            max_transfer_outputs=args.max_transfer_outputs,
            max_transfer_records=args.max_transfer_records,
        ),
    )
    write_result = write_codex_package_ledger(
        ledger=ledger,
        out_json=args.out_json or None,
        out_md=args.out_md or None,
        ledger_root=args.ledger_root,
        apply=args.write,
        confirm=args.confirm,
    )
    payload = {
        "ok": bool(ledger.get("ok")) and bool(write_result.get("ok")),
        "dry_run": not args.write,
        "ledger": ledger,
        "write": write_result,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
