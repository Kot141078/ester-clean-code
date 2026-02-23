# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.garage import agent_queue, agent_supervisor
from modules.garage.templates import create_agent_from_template
from modules.runtime import execution_window
from modules.thinking import action_registry


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _item_by_queue_id(state: Dict[str, Any], queue_id: str) -> Dict[str, Any]:
    qid = str(queue_id or "").strip()
    if not qid:
        return {}
    return dict((state.get("items_by_id") or {}).get(qid) or {})


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_agent_queue_approval_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    garage_root = (tmp_root / "garage").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    garage_root.mkdir(parents=True, exist_ok=True)

    env_keys = [
        "PERSIST_DIR",
        "GARAGE_ROOT",
        "ESTER_VOLITION_SLOT",
        "ESTER_VOLITION_ALLOWED_HOURS",
        "ESTER_ALLOW_OUTBOUND_NETWORK",
        "ESTER_ORACLE_ENABLE",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    os.environ["ESTER_ORACLE_ENABLE"] = "0"

    try:
        create_rep = create_agent_from_template(
            "clawbot.safe.v1",
            {
                "name": "iter71.approval.smoke",
                "owner": "tools.agent_queue_approval_smoke",
                "goal": "Approval gate smoke",
            },
            dry_run=False,
        )
        agent_id = str(create_rep.get("agent_id") or "").strip()

        safe_plan = {
            "schema": "ester.plan.v1",
            "plan_id": "iter71_queue_approval",
            "steps": [
                {
                    "action": "messages.outbox.enqueue",
                    "args": {
                        "kind": "smoke.approval",
                        "text": "iter71 queue approval smoke",
                        "meta": {"source": "tools.agent_queue_approval_smoke"},
                    },
                }
            ],
        }

        enqueue_rep = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "agent_id": agent_id,
                "actor": "ester:smoke",
                "reason": "iter71_approval_enqueue",
                "challenge_sec": 0,
                "plan": safe_plan,
            },
        )
        queue_id = str(enqueue_rep.get("queue_id") or "").strip()

        state_before = agent_queue.fold_state()
        item_before = _item_by_queue_id(state_before, queue_id)

        open_rep = execution_window.open_window(
            actor="ester:smoke",
            reason="iter71_queue_approval_open",
            ttl_sec=30,
            budget_seconds=60,
            budget_energy=5,
        )
        window_id = str(open_rep.get("window_id") or "")

        tick_before = agent_supervisor.tick_once(actor="ester:smoke", reason="iter71_before_approve", dry_run=False)
        state_blocked = agent_queue.fold_state()
        item_blocked = _item_by_queue_id(state_blocked, queue_id)

        approve_rep = action_registry.invoke(
            "agent.queue.approve",
            {
                "queue_id": queue_id,
                "actor": "ester:smoke",
                "reason": "iter71_smoke_approve",
            },
        )
        approve_idem = action_registry.invoke(
            "agent.queue.approve",
            {
                "queue_id": queue_id,
                "actor": "ester:smoke",
                "reason": "iter71_smoke_approve_again",
            },
        )

        tick_after = agent_supervisor.tick_once(actor="ester:smoke", reason="iter71_after_approve", dry_run=False)
        state_after = agent_queue.fold_state()
        item_after = _item_by_queue_id(state_after, queue_id)

        close_rep: Dict[str, Any]
        if window_id:
            close_rep = execution_window.close_window(window_id, actor="ester:smoke", reason="cleanup")
        else:
            close_rep = {"ok": True, "note": "window_not_open"}

        queue_events = _read_jsonl(agent_queue.queue_path())
        approve_events = [
            row
            for row in queue_events
            if str(row.get("queue_id") or "").strip() == queue_id
            and str(row.get("type") or row.get("event") or "").strip().lower() == "approve"
        ]
        claim_events_before = [
            row
            for row in queue_events
            if str(row.get("queue_id") or "").strip() == queue_id
            and str(row.get("type") or "").strip().lower() == "claim"
        ]

        blocked_before = (
            bool(tick_before.get("ok"))
            and (not bool(tick_before.get("ran")))
            and (str(tick_before.get("blocked") or "") == "approval")
            and (str(tick_before.get("policy_hit") or "") == "queue_blocked_approval")
        )
        executed_after = bool(tick_after.get("ok")) and bool(tick_after.get("ran"))
        requires_approval_set = bool(item_before.get("requires_approval")) and (not bool(item_before.get("approved")))
        still_unclaimed_before_approve = (str(item_blocked.get("status") or "") == "enqueued")
        approve_ok = bool(approve_rep.get("ok")) and bool(approve_rep.get("approved"))
        approve_idem_ok = bool(approve_idem.get("ok")) and bool(approve_idem.get("approved"))
        final_done_ok = (str(item_after.get("status") or "") == "done") and bool(item_after.get("approved"))

        ok = (
            bool(create_rep.get("ok"))
            and bool(agent_id)
            and bool(enqueue_rep.get("ok"))
            and bool(queue_id)
            and bool(open_rep.get("ok"))
            and blocked_before
            and requires_approval_set
            and still_unclaimed_before_approve
            and approve_ok
            and approve_idem_ok
            and executed_after
            and final_done_ok
            and (len(approve_events) >= 1)
            and bool(close_rep.get("ok"))
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "queue_id": queue_id,
            "create": create_rep,
            "enqueue": enqueue_rep,
            "open_window": open_rep,
            "tick_before": tick_before,
            "approve": approve_rep,
            "approve_idempotent": approve_idem,
            "tick_after": tick_after,
            "close_window": close_rep,
            "state_before_item": item_before,
            "state_blocked_item": item_blocked,
            "state_after_item": item_after,
            "events_summary": {
                "total": len(queue_events),
                "approve_events": len(approve_events),
                "claim_events_total": len(claim_events_before),
            },
            "checks": {
                "requires_approval_set": bool(requires_approval_set),
                "blocked_before": bool(blocked_before),
                "still_unclaimed_before_approve": bool(still_unclaimed_before_approve),
                "approve_ok": bool(approve_ok),
                "approve_idem_ok": bool(approve_idem_ok),
                "executed_after": bool(executed_after),
                "final_done_ok": bool(final_done_ok),
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
