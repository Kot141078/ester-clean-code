# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.memory.core_sqlite import MemoryCore, default_import_paths


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Import legacy Ester memory into the sidecar SQLite core.")
    defaults = default_import_paths()
    p.add_argument("--db", default="", help="Target SQLite path. Defaults to ESTER_MEMORY_CORE_PATH or data/memory_core/ester_memory.sqlite")
    p.add_argument("--snapshot", default=defaults["snapshot"])
    p.add_argument("--clean-memory", default=defaults["clean_memory"])
    p.add_argument("--journal", default=defaults["journal"])
    p.add_argument("--anchor", default=defaults["anchor"])
    p.add_argument("--core-facts", default=defaults["core_facts"])
    p.add_argument("--identity-dynamic", default=defaults["identity_dynamic"])
    p.add_argument("--status-only", action="store_true", help="Print DB status and exit")
    return p


def main() -> int:
    args = _build_parser().parse_args()
    core = MemoryCore(path=args.db or None)
    try:
        if args.status_only:
            print(json.dumps(core.status(), ensure_ascii=False, indent=2))
            return 0
        report = core.import_all(
            snapshot=Path(args.snapshot),
            clean_memory=Path(args.clean_memory),
            journal=Path(args.journal),
            anchor=Path(args.anchor),
            core_facts=Path(args.core_facts),
            identity_dynamic=Path(args.identity_dynamic),
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ok") else 1
    finally:
        core.close()


if __name__ == "__main__":
    raise SystemExit(main())
