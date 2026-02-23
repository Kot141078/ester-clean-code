# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.proactivity.executor import run_once


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "on", "y"}:
        return True
    if s in {"0", "false", "no", "off", "n"}:
        return False
    return bool(default)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Iter42 proactivity tick: initiative -> plan -> enqueue (no execution).")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--plan-only", action="store_true", help="Force plan-only mode (no enqueue).")
    grp.add_argument("--enqueue", action="store_true", help="Force enqueue mode.")

    ap.add_argument("--max-work-ms", type=int, default=None, help="Planning budget cap (ms).")
    ap.add_argument("--max-queue-size", type=int, default=None, help="Guard: skip enqueue if live queue >= this value.")
    ap.add_argument("--cooldown-sec", type=int, default=None, help="Dedupe cooldown by (initiative_id, plan_hash).")

    ap.add_argument("--dry-run", action="store_true", help="Dry-run: no state writes except volition journal.")
    ap.add_argument("--dry", default="", help="Legacy alias: 1/0.")

    args = ap.parse_args(argv)

    mode = "enqueue"
    if bool(args.plan_only):
        mode = "plan_only"
    elif bool(args.enqueue):
        mode = "enqueue"

    dry = bool(args.dry_run)
    if str(args.dry or "").strip() != "":
        dry = _as_bool(args.dry, dry)

    rep = run_once(
        dry=dry,
        mode=mode,
        max_work_ms=args.max_work_ms,
        max_queue_size=args.max_queue_size,
        cooldown_sec=args.cooldown_sec,
    )
    print(json.dumps(rep, ensure_ascii=True, indent=2))
    return 0 if bool(rep.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
