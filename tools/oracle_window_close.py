# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import oracle_window


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Close Oracle Window.")
    ap.add_argument("--window-id", required=True)
    ap.add_argument("--reason", default="")
    args = ap.parse_args(argv)

    rep = oracle_window.close_window(
        window_id=str(args.window_id or "").strip(),
        actor="tool.oracle_window_close",
        reason=str(args.reason or ""),
    )
    print(json.dumps(rep, ensure_ascii=True, indent=2))
    return 0 if bool(rep.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
