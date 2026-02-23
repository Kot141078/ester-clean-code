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


def _mask(value: str) -> str:
    s = str(value or "")
    if len(s) <= 6:
        return s
    return s[:4] + "..." + s[-2:]


def _as_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Open Oracle Window (disabled by default).")
    ap.add_argument("--reason", required=True, help="why open window is needed")
    ap.add_argument("--ttl-sec", type=int, default=600)
    ap.add_argument("--max-calls", type=int, default=3)
    ap.add_argument("--max-tokens-in", type=int, default=8000)
    ap.add_argument("--max-tokens-out", type=int, default=2000)
    ap.add_argument("--allow-agents", default="0", help="0/1")
    args = ap.parse_args(argv)

    rep = oracle_window.open_window(
        reason=str(args.reason or "").strip(),
        actor="tool.oracle_window_open",
        budgets={
            "ttl_sec": int(args.ttl_sec),
            "max_calls": int(args.max_calls),
            "max_est_tokens_in_total": int(args.max_tokens_in),
            "max_tokens_out_total": int(args.max_tokens_out),
        },
        allow_agents=_as_bool(args.allow_agents),
        meta={"source": "tools.oracle_window_open"},
    )

    out = dict(rep)
    if out.get("window_id"):
        out["window_id_masked"] = _mask(str(out.get("window_id")))
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if bool(rep.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
