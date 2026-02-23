# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.garage import agent_factory, agent_queue, agent_runner
from modules.garage.templates import create_agent_from_template


def _find_item(st: Dict[str, Any], queue_id: str) -> Dict[str, Any]:
    qid = str(queue_id or "").strip()
    if not qid:
        return {}
    for row in list(st.get("items") or []):
        item = dict(row or {})
        if str(item.get("queue_id") or "").strip() == qid:
            return item
    return {}


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_agent_disable_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    garage_root = (tmp_root / "garage").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    garage_root.mkdir(parents=True, exist_ok=True)

    env_keys = ["PERSIST_DIR", "GARAGE_ROOT", "ESTER_VOLITION_SLOT", "ESTER_ALLOW_OUTBOUND_NETWORK"]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_VOLITION_SLOT"] = "A"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"

    try:
        create_rep = create_agent_from_template(
            "builder.v1",
            {
                "name": "iter70.disable.smoke",
                "owner": "tools.agent_disable_smoke",
                "goal": "validate disable enforcement",
            },
            dry_run=False,
        )
        agent_id = str(create_rep.get("agent_id") or "").strip()

        plan = {
            "steps": [
                {
                    "action_id": "files.sandbox_write",
                    "args": {"relpath": "iter70_disable_smoke.txt", "content": "disable smoke"},
                }
            ]
        }

        enqueue_before = agent_queue.enqueue(
            plan,
            priority=80,
            challenge_sec=0,
            actor="tools.agent_disable_smoke",
            reason="before_disable",
            agent_id=agent_id,
        )
        queue_id = str(enqueue_before.get("queue_id") or "").strip()
        fold_before = agent_queue.fold_state()
        canceled_before = int((fold_before.get("stats") or {}).get("canceled") or 0)

        disable_rep = agent_factory.disable_agent(agent_id, reason="smoke")
        enqueue_after = agent_queue.enqueue(
            plan,
            priority=80,
            challenge_sec=0,
            actor="tools.agent_disable_smoke",
            reason="after_disable",
            agent_id=agent_id,
        )
        select_after = agent_queue.select_next(now_ts=int(time.time()))
        run_after = agent_runner.run_once(agent_id, plan, {"intent": "agent_disable_smoke"})
        fold_after = agent_queue.fold_state()
        canceled_after = int((fold_after.get("stats") or {}).get("canceled") or 0)
        canceled_delta = int(canceled_after - canceled_before)

        item_after = _find_item(fold_after, queue_id)
        item_status = str(item_after.get("status") or "").strip()

        enqueue_blocked = (not bool(enqueue_after.get("ok"))) and (str(enqueue_after.get("error") or "") == "agent_disabled")
        select_safe = not (
            bool(select_after.get("found"))
            and str((dict(select_after.get("candidate") or {})).get("agent_id") or "").strip() == agent_id
        )
        run_blocked = (not bool(run_after.get("ok"))) and (str(run_after.get("error_code") or "") == "AGENT_DISABLED")
        disable_canceled_ok = int(disable_rep.get("canceled") or 0) >= 1
        cancel_state_ok = (canceled_delta >= 1) or (item_status == "canceled")

        ok = (
            bool(create_rep.get("ok"))
            and bool(agent_id)
            and bool(enqueue_before.get("ok"))
            and bool(queue_id)
            and bool(disable_rep.get("ok"))
            and disable_canceled_ok
            and enqueue_blocked
            and select_safe
            and run_blocked
            and cancel_state_ok
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "queue_id": queue_id,
            "create": {"ok": bool(create_rep.get("ok")), "path": str(create_rep.get("path") or "")},
            "enqueue_before": enqueue_before,
            "disable": disable_rep,
            "enqueue_after": enqueue_after,
            "select_after": select_after,
            "run_after": run_after,
            "fold_before_stats": dict(fold_before.get("stats") or {}),
            "fold_after_stats": dict(fold_after.get("stats") or {}),
            "queue_item_status_after_disable": item_status,
            "checks": {
                "disable_canceled_ok": bool(disable_canceled_ok),
                "enqueue_blocked": bool(enqueue_blocked),
                "select_safe": bool(select_safe),
                "run_blocked": bool(run_blocked),
                "cancel_state_ok": bool(cancel_state_ok),
            },
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        for key, val in old_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
