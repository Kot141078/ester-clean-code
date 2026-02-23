# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import execution_window


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_execution_window_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)

    old_persist = os.environ.get("PERSIST_DIR")
    os.environ["PERSIST_DIR"] = str(persist_dir)
    try:
        s0 = execution_window.status()

        open_a = execution_window.open_window(
            actor="ester:smoke",
            reason="execution_window_smoke_ttl",
            ttl_sec=2,
            budget_seconds=2,
            budget_energy=2,
        )
        wid_a = str(open_a.get("window_id") or "")
        s1 = execution_window.status()
        time.sleep(2.2)
        s2 = execution_window.status()

        open_b = execution_window.open_window(
            actor="ester:smoke",
            reason="execution_window_smoke_close",
            ttl_sec=30,
            budget_seconds=30,
            budget_energy=3,
        )
        wid_b = str(open_b.get("window_id") or "")
        close_b = execution_window.close_window(wid_b, actor="ester:smoke", reason="cleanup")
        s3 = execution_window.status()

        ok = (
            bool(s0.get("ok"))
            and (not bool(s0.get("open")))
            and bool(open_a.get("ok"))
            and bool(wid_a)
            and bool(s1.get("open"))
            and (str(s1.get("window_id") or "") == wid_a)
            and (not bool(s2.get("open")))
            and bool(open_b.get("ok"))
            and bool(wid_b)
            and bool(close_b.get("ok"))
            and (not bool(s3.get("open")))
        )
        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "status_initial": s0,
            "open_ttl": open_a,
            "status_open": s1,
            "status_after_ttl": s2,
            "open_for_close": open_b,
            "close": close_b,
            "status_after_close": s3,
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        if old_persist is None:
            os.environ.pop("PERSIST_DIR", None)
        else:
            os.environ["PERSIST_DIR"] = old_persist
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
