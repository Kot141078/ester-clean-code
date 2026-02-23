# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from modules.curiosity import executor as curiosity_executor


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run one curiosity pipeline tick.")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--plan-only", action="store_true", help="Build plan only, do not enqueue.")
    mode.add_argument("--enqueue", action="store_true", help="Build plan and enqueue (default).")
    p.add_argument("--max-work-ms", type=int, default=None, help="Override max work budget.")
    p.add_argument("--max-queue-size", type=int, default=None, help="Override max queue size guard.")
    p.add_argument("--cooldown-sec", type=int, default=None, help="Override dedupe cooldown seconds.")
    p.add_argument("--dry-run", action="store_true", help="Run without creating agent/queue side effects.")
    p.add_argument("--json", action="store_true", help="Print full JSON result.")
    return p


def _mode_from_args(args: argparse.Namespace) -> str:
    if bool(args.plan_only):
        return "plan_only"
    return "enqueue"


def _print_human(rep: Dict[str, Any]) -> None:
    ok = bool(rep.get("ok"))
    reason = str(rep.get("reason") or "")
    ticket_id = str(rep.get("ticket_id") or "")
    plan_id = str(rep.get("plan_id") or "")
    enqueue_id = str(rep.get("enqueue_id") or "")
    slot = str(rep.get("slot") or "")
    queue_size = int(rep.get("queue_size") or 0)
    print(
        "ok={ok} reason={reason} ticket_id={ticket_id} plan_id={plan_id} enqueue_id={enqueue_id} slot={slot} queue_size={queue_size}".format(
            ok=int(ok),
            reason=reason or "n/a",
            ticket_id=ticket_id or "n/a",
            plan_id=plan_id or "n/a",
            enqueue_id=enqueue_id or "n/a",
            slot=slot or "n/a",
            queue_size=queue_size,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    rep = curiosity_executor.run_once(
        mode=_mode_from_args(args),
        max_work_ms=args.max_work_ms,
        max_queue_size=args.max_queue_size,
        cooldown_sec=args.cooldown_sec,
        dry_run=bool(args.dry_run),
    )
    if bool(args.json):
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        _print_human(rep)
    return 0 if bool(rep.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
