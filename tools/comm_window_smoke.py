# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import comm_window


def main() -> int:
    opened = comm_window.open_window(
        kind="telegram",
        ttl_sec=10,
        reason="comm_window_smoke",
        allow_hosts=["api.telegram.org"],
    )
    wid = str(opened.get("window_id") or "")
    st1 = comm_window.is_open(wid)
    closed = comm_window.close_window(wid)
    st2 = comm_window.is_open(wid)

    ok = (
        bool(opened.get("ok"))
        and bool(st1.get("ok"))
        and bool(st1.get("open"))
        and int(st1.get("remaining") or 0) > 0
        and bool(closed.get("ok"))
        and bool(st2.get("ok"))
        and (not bool(st2.get("open")))
    )
    out = {
        "ok": ok,
        "open": opened,
        "is_open_before_close": st1,
        "close": closed,
        "is_open_after_close": st2,
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

