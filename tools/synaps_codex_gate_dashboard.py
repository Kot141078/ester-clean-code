#!/usr/bin/env python3
"""Build a read-only dashboard from SYNAPS Codex package ledgers."""

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
        CODEX_GATE_DASHBOARD_CONFIRM_PHRASE,
        CodexGateDashboardPolicy,
        build_codex_gate_dashboard,
        write_codex_gate_dashboard,
    )

    parser = argparse.ArgumentParser(description="Summarize open SYNAPS Codex package ledgers.")
    parser.add_argument("--ledger", action="append", default=[], help="Package ledger JSON. Repeatable.")
    parser.add_argument("--ledger-root", default="data/synaps/codex_bridge/package_ledgers")
    parser.add_argument("--include-root", action="store_true", help="Include *.json ledgers from --ledger-root.")
    parser.add_argument("--max-ledgers", type=int, default=128)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--confirm", default="", help=f"Required for --write: {CODEX_GATE_DASHBOARD_CONFIRM_PHRASE}")
    args = parser.parse_args(argv)

    dashboard = build_codex_gate_dashboard(
        ledger_paths=args.ledger,
        ledger_root=args.ledger_root,
        include_root=args.include_root,
        policy=CodexGateDashboardPolicy(max_ledgers=args.max_ledgers),
    )
    write = write_codex_gate_dashboard(
        dashboard=dashboard,
        out_json=args.out_json or None,
        out_md=args.out_md or None,
        apply=args.write,
        confirm=args.confirm,
    )
    payload = {
        "ok": bool(dashboard.get("ok")) and bool(write.get("ok")),
        "dry_run": not args.write,
        "dashboard": dashboard,
        "write": write,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
