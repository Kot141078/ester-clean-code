# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Read Ester memory diagnostics overview.")
    parser.add_argument("--section", choices=("overview", "health", "timeline", "operator", "reply_trace", "self_diagnostics"), default="overview")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    args = parser.parse_args()

    root = os.getcwd()
    if root not in sys.path:
        sys.path.insert(0, root)

    from modules.memory import memory_index

    memory_index.ensure_materialized()
    if args.section == "overview":
        path = memory_index.overview_path() if args.json else memory_index.overview_digest_path()
    elif args.section == "health":
        path = memory_index.health_path() if args.json else memory_index.health_digest_path()
    elif args.section == "timeline":
        path = memory_index.timeline_path() if args.json else memory_index.timeline_digest_path()
    elif args.section == "reply_trace":
        from modules.memory import reply_trace

        path = Path(reply_trace.latest_path()) if args.json else Path(reply_trace.latest_digest_path())
    elif args.section == "self_diagnostics":
        from modules.memory import self_diagnostics

        self_diagnostics.ensure_materialized()
        path = Path(self_diagnostics.latest_path()) if args.json else Path(self_diagnostics.latest_digest_path())
    else:
        path = memory_index.operator_path() if args.json else memory_index.operator_digest_path()

    if not path.exists():
        if args.json:
            print(json.dumps({"ok": True, "state": "not_materialized", "path": str(path)}, ensure_ascii=False, indent=2))
        else:
            print(f"# {args.section}\n\n- state: not_materialized\n- path: `{path}`")
        return 0

    text = path.read_text(encoding="utf-8")
    if args.json:
        print(json.dumps(json.loads(text), ensure_ascii=False, indent=2))
    else:
        print(text.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
