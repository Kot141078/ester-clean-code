#!/usr/bin/env python3
"""Evaluate a read-only stale policy for open SYNAPS Codex gates."""

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
        CODEX_GATE_STALE_POLICY_CONFIRM_PHRASE,
        CodexGateStalePolicy,
        evaluate_codex_gate_stale_policy_file,
        write_codex_gate_stale_policy,
    )

    parser = argparse.ArgumentParser(description="Evaluate stale open SYNAPS Codex package gates.")
    parser.add_argument("--dashboard", required=True, help="Gate dashboard JSON from synaps_codex_gate_dashboard.py.")
    parser.add_argument("--max-peer-silent-open", type=int, default=3)
    parser.add_argument("--stale-after-hours", type=float, default=6.0)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--confirm", default="", help=f"Required for --write: {CODEX_GATE_STALE_POLICY_CONFIRM_PHRASE}")
    args = parser.parse_args(argv)

    evaluation = evaluate_codex_gate_stale_policy_file(
        dashboard_path=args.dashboard,
        policy=CodexGateStalePolicy(
            max_peer_silent_open=args.max_peer_silent_open,
            stale_after_hours=args.stale_after_hours,
        ),
    )
    write = write_codex_gate_stale_policy(
        evaluation=evaluation,
        out_json=args.out_json or None,
        out_md=args.out_md or None,
        apply=args.write,
        confirm=args.confirm,
    )
    payload = {
        "ok": bool(evaluation.get("ok")) and bool(write.get("ok")),
        "dry_run": not args.write,
        "evaluation": evaluation,
        "write": write,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
