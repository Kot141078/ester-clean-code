# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from growth_engine_ester.outcome_candidates import accept_candidate, reject_candidate  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Accept or reject a pending SRLM outcome candidate.")
    parser.add_argument("--candidate-id", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--accept", action="store_true")
    action.add_argument("--reject", action="store_true")
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--outcome-id", default="", help="Optional accepted outcome_id.")
    parser.add_argument("--root", default=None, help="Optional SRLM root. Defaults to ESTER_SRLM_ROOT/data/srlm.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = {
        "candidate_id": args.candidate_id,
        "reviewed_by": args.reviewed_by,
        "review_note": args.note,
    }
    if args.outcome_id:
        payload["outcome_id"] = args.outcome_id
    if args.accept:
        result = accept_candidate(payload, root=args.root)
    else:
        result = reject_candidate(payload, root=args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
