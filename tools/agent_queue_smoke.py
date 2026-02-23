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

from modules.garage import agent_queue


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_agent_queue_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)

    old_persist = os.environ.get("PERSIST_DIR")
    os.environ["PERSIST_DIR"] = str(persist_dir)
    try:
        enqueue_rep = agent_queue.enqueue(
            {
                "steps": [
                    {
                        "action_id": "files.sandbox_write",
                        "args": {"relpath": "smoke_queue.txt", "content": "ok"},
                    }
                ]
            },
            priority=70,
            challenge_sec=2,
            actor="ester:smoke",
            reason="agent_queue_smoke",
            agent_id="agent_queue_smoke",
        )
        qid = str(enqueue_rep.get("queue_id") or "")

        sel_a = agent_queue.select_next(now_ts=int(time.time()))
        time.sleep(2.1)
        sel_b = agent_queue.select_next(now_ts=int(time.time()))
        folded = agent_queue.fold_state()

        ok = (
            bool(enqueue_rep.get("ok"))
            and bool(qid)
            and (not bool(sel_a.get("found")))
            and (str(sel_a.get("reason") or "") == "challenge_window")
            and (str(sel_a.get("queue_id") or "") == qid)
            and bool(sel_b.get("found"))
            and (str((sel_b.get("candidate") or {}).get("queue_id") or "") == qid)
            and (int((folded.get("stats") or {}).get("enqueued") or 0) >= 1)
        )
        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "queue_path": str(agent_queue.queue_path()),
            "enqueue": enqueue_rep,
            "select_before": sel_a,
            "select_after": sel_b,
            "folded": {
                "events_total": int(folded.get("events_total") or 0),
                "items_total": int(folded.get("items_total") or 0),
                "stats": dict(folded.get("stats") or {}),
            },
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
