# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from growth_engine_ester.outcome_candidates import propose_candidate  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Propose a bounded SRLM outcome candidate for later review.")
    parser.add_argument("--source", required=True, choices=["human", "reality", "l4", "model", "judge"])
    parser.add_argument("--kind", required=True, help="Outcome candidate event_kind, e.g. reality.tool.success")
    parser.add_argument("--score", required=True, type=float)
    parser.add_argument("--uncertainty", default=0.0, type=float)
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--reason", default="bounded event may represent a real fitness outcome")
    parser.add_argument("--candidate-id", default="")
    parser.add_argument("--root", default=None, help="Optional SRLM root. Defaults to ESTER_SRLM_ROOT/data/srlm.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = {
        "source": args.source,
        "event_kind": args.kind,
        "score": args.score,
        "uncertainty": args.uncertainty,
        "source_ref": args.source_ref,
        "notes": args.note,
        "reason": args.reason,
    }
    if args.candidate_id:
        payload["candidate_id"] = args.candidate_id
    result = propose_candidate(payload, root=args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
