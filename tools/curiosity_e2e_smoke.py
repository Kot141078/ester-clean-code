# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
import sys
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_SMOKE_PERSIST_DIR = (_REPO_ROOT / "data" / "curiosity_smoke").resolve()
os.environ["PERSIST_DIR"] = str(_SMOKE_PERSIST_DIR)

from modules.curiosity import executor as curiosity_executor
from modules.curiosity import unknown_detector
from modules.garage import agent_queue, agent_supervisor
from modules.runtime import execution_window
from modules.runtime import network_deny


def _fail(code: str, detail: str, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {"ok": False, "error": code, "detail": detail, "extra": dict(extra or {})}


def _close_window_safe() -> None:
    try:
        cur = execution_window.current_window()
        if bool(cur.get("open")) and str(cur.get("window_id") or "").strip():
            execution_window.close_window(
                str(cur.get("window_id") or ""),
                actor="ester",
                reason="curiosity_e2e_smoke_cleanup",
            )
    except Exception:
        return


def _queue_item(queue_id: str) -> Dict[str, Any]:
    st = agent_queue.fold_state()
    return dict((st.get("items_by_id") or {}).get(str(queue_id or ""), {}) or {})


def main() -> int:
    shutil.rmtree(_SMOKE_PERSIST_DIR, ignore_errors=True)
    _SMOKE_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["ESTER_OFFLINE"] = "1"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    os.environ["ESTER_CURIOSITY_WEB_ENABLE"] = "0"
    os.environ["ESTER_CURIOSITY_CHALLENGE_SEC"] = "0"

    _close_window_safe()
    start_deny = int((network_deny.get_stats() or {}).get("deny_count") or 0)
    start_events = len(unknown_detector.ticket_events())

    query = "curiosity-e2e-miss-" + uuid.uuid4().hex
    open_rep = unknown_detector.maybe_open_ticket(
        query,
        source="pending",
        context_text="curiosity_e2e_smoke",
        recall_score=0.0,
        thresholds={"memory_miss_max": 1.0, "dedupe_sec": 0},
        budgets={"max_depth": 2, "max_hops": 2, "max_docs": 8, "max_work_ms": 1800},
    )
    if not bool(open_rep.get("opened")):
        rep = _fail("ticket_open_failed", str(open_rep.get("reason") or "unknown"), {"open_rep": open_rep})
        print(json.dumps(rep, ensure_ascii=True, indent=2))
        print("FAIL")
        return 2
    ticket_id = str(open_rep.get("ticket_id") or "")

    events_after_open = len(unknown_detector.ticket_events())
    if events_after_open <= start_events:
        rep = _fail("ticket_log_not_appended", "tickets.jsonl did not grow after ticket open", {"ticket_id": ticket_id})
        print(json.dumps(rep, ensure_ascii=True, indent=2))
        print("FAIL")
        return 2

    enqueue_rep: Dict[str, Any] = {}
    enqueue_id = ""
    for _ in range(12):
        enqueue_rep = curiosity_executor.run_once(
            mode="enqueue",
            max_work_ms=2500,
            max_queue_size=100000,
            cooldown_sec=0,
            dry_run=False,
        )
        if bool(enqueue_rep.get("ok")) and str(enqueue_rep.get("ticket_id") or "") == ticket_id:
            if str(enqueue_rep.get("reason") or "") in {"enqueued", "cooldown_dedupe", "queue_full"}:
                enqueue_id = str(enqueue_rep.get("enqueue_id") or "")
                break
        time.sleep(0.05)

    if not enqueue_id:
        rep = _fail(
            "enqueue_missing",
            "ticket was not enqueued by curiosity run_once",
            {"ticket_id": ticket_id, "last_rep": enqueue_rep},
        )
        print(json.dumps(rep, ensure_ascii=True, indent=2))
        print("FAIL")
        return 2

    qitem_before_window = _queue_item(enqueue_id)
    status_before_window = str(qitem_before_window.get("status") or "")
    if status_before_window in {"running", "done", "failed"}:
        rep = _fail(
            "unexpected_execution_before_window",
            "queue item progressed before execution window opened",
            {"queue_id": enqueue_id, "status": status_before_window},
        )
        print(json.dumps(rep, ensure_ascii=True, indent=2))
        print("FAIL")
        return 2

    open_window_rep = execution_window.open_window(
        actor="ester",
        reason="curiosity_e2e_smoke",
        ttl_sec=90,
        budget_seconds=120,
        budget_energy=20,
        meta={"mode": "local_only", "source": "curiosity_e2e_smoke"},
    )
    if not bool(open_window_rep.get("ok")):
        rep = _fail("window_open_failed", str(open_window_rep.get("error") or "window_open_failed"))
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        print("FAIL")
        return 2

    try:
        done = False
        supervisor_reps: list[Dict[str, Any]] = []
        for _ in range(24):
            srep = agent_supervisor.tick_once(actor="ester", reason="curiosity_e2e_smoke")
            supervisor_reps.append(dict(srep or {}))
            qitem = _queue_item(enqueue_id)
            qstatus = str(qitem.get("status") or "")
            if qstatus in {"done", "failed", "canceled", "expired"}:
                done = True
                break
            time.sleep(0.1)

        if not done:
            rep = _fail(
                "queue_not_completed",
                "queue item did not complete during open execution window",
                {"queue_id": enqueue_id, "supervisor_tail": supervisor_reps[-3:]},
            )
            print(json.dumps(rep, ensure_ascii=True, indent=2))
            print("FAIL")
            return 2
    finally:
        _close_window_safe()

    final_item = _queue_item(enqueue_id)
    final_qstatus = str(final_item.get("status") or "")
    if final_qstatus != "done":
        rep = _fail(
            "queue_execution_failed",
            "queue item finished with non-done status",
            {"queue_id": enqueue_id, "status": final_qstatus, "item": final_item},
        )
        print(json.dumps(rep, ensure_ascii=True, indent=2))
        print("FAIL")
        return 2

    folded = unknown_detector.fold_tickets()
    ticket = dict((folded.get("tickets_by_id") or {}).get(ticket_id, {}) or {})
    ticket_status = str(ticket.get("status") or "")
    result = dict(ticket.get("result") or {})
    evidence_ref = dict(result.get("evidence_ref") or {})
    l4w_hash = str(evidence_ref.get("l4w_envelope_hash") or "")
    evidence_sha = str(evidence_ref.get("sha256") or "")
    if ticket_status != "resolved":
        rep = _fail("ticket_not_resolved", "ticket did not resolve", {"ticket_id": ticket_id, "ticket": ticket})
        print(json.dumps(rep, ensure_ascii=True, indent=2))
        print("FAIL")
        return 2
    if not evidence_sha or not l4w_hash:
        rep = _fail(
            "missing_evidence_or_l4w",
            "resolved ticket does not contain full evidence_ref",
            {"ticket_id": ticket_id, "result": result},
        )
        print(json.dumps(rep, ensure_ascii=True, indent=2))
        print("FAIL")
        return 2

    end_deny = int((network_deny.get_stats() or {}).get("deny_count") or 0)
    if end_deny != start_deny:
        rep = _fail(
            "network_deny_changed",
            "deny_count changed during local-only smoke",
            {"deny_before": start_deny, "deny_after": end_deny},
        )
        print(json.dumps(rep, ensure_ascii=True, indent=2))
        print("FAIL")
        return 2

    rep = {
        "ok": True,
        "ticket_id": ticket_id,
        "enqueue_id": enqueue_id,
        "queue_status": final_qstatus,
        "ticket_status": ticket_status,
        "result_kind": str(result.get("kind") or ""),
        "evidence_sha256": evidence_sha,
        "l4w_envelope_hash": l4w_hash,
        "deny_count_before": start_deny,
        "deny_count_after": end_deny,
    }
    print(json.dumps(rep, ensure_ascii=True, indent=2))
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
