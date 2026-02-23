# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime.status_iter18 import background_tick_once, runtime_status


def _as_bool(s: str) -> bool:
    return str(s).strip().lower() in {"1", "true", "yes", "on", "y"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", default="0", help="1/0")
    args = ap.parse_args(argv)

    rep = background_tick_once(dry=_as_bool(args.dry))
    out = {"tick": rep, "status": runtime_status()}
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if rep.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
