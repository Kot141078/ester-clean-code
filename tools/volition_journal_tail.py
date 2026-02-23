# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.volition.journal import journal_path


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Print last N volition decisions with optional filters.")
    ap.add_argument("-n", "--limit", type=int, default=20, help="tail size")
    ap.add_argument("--agent-id", default="", help="filter by agent_id")
    ap.add_argument("--plan-id", default="", help="filter by plan_id")
    args = ap.parse_args(argv)

    path = journal_path()
    rows: list[dict] = []
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)

    want_agent = str(args.agent_id or "").strip()
    want_plan = str(args.plan_id or "").strip()
    if want_agent:
        rows = [
            r
            for r in rows
            if str(r.get("agent_id") or ((r.get("metadata") or {}).get("agent_id") or "")).strip() == want_agent
        ]
    if want_plan:
        rows = [
            r
            for r in rows
            if str(r.get("plan_id") or ((r.get("metadata") or {}).get("plan_id") or "")).strip() == want_plan
        ]

    rows = rows[-max(1, int(args.limit or 20)) :]
    print(f"# {path}")
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
