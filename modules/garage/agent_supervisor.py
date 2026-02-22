# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict

from modules.garage import agent_factory, agent_queue, agent_runner
from modules.runtime import execution_window
from modules.volition import journal as volition_journal


def _slot() -> str:
    return str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper() or "A"


def _actor_allowed(actor: str) -> bool:
    a = str(actor or "").strip().lower()
    return bool(a == "ester" or a.startswith("ester:"))


def _journal(
    *,
    actor: str,
    reason: str,
    policy_hit: str,
    allowed: bool,
    reason_code: str,
    reason_text: str,
    chain_id: str,
    queue_id: str = "",
    window_id: str = "",
    agent_id: str = "",
    run_id: str = "",
    extra: Dict[str, Any] | None = None,
    duration_ms: int = 0,
) -> Dict[str, Any]:
    row = {
        "id": "vol_sup_" + uuid.uuid4().hex,
        "ts": int(time.time()),
        "chain_id": chain_id,
        "step": "supervisor",
        "actor": str(actor or "ester"),
        "intent": str(reason or "supervisor_tick"),
        "action_kind": "agent.supervisor.tick_once",
        "allowed": bool(allowed),
        "reason_code": str(reason_code or ""),
        "reason": str(reason_text or ""),
        "slot": _slot(),
        "metadata": {
            "policy_hit": str(policy_hit or ""),
            "queue_id": str(queue_id or ""),
            "window_id": str(window_id or ""),
            "agent_id": str(agent_id or ""),
            "run_id": str(run_id or ""),
            **dict(extra or {}),
        },
        "agent_id": str(agent_id or ""),
        "action_id": "agent.supervisor.tick_once",
        "decision": ("allow" if bool(allowed) else "deny"),
        "policy_hit": str(policy_hit or ""),
        "duration_ms": int(duration_ms or 0),
    }
    volition_journal.append(row)
    return row


def tick_once(*, actor: str = "ester", reason: str = "", dry_run: bool = False) -> Dict[str, Any]:
    start_mon = time.monotonic()
    now = int(time.time())
    clean_actor = str(actor or "ester").strip() or "ester"
    clean_reason = str(reason or "supervisor_tick").strip() or "supervisor_tick"
    chain_id = "chain_supervisor_" + uuid.uuid4().hex[:10]
    maintenance: Dict[str, Any] = {}

    try:
        maintenance = agent_factory.garage_maintenance(actor=clean_actor)
    except Exception as exc:
        maintenance = {"ok": False, "error": f"maintenance_failed:{exc.__class__.__name__}"}

    if not _actor_allowed(clean_actor):
        _journal(
            actor=clean_actor,
            reason=clean_reason,
            policy_hit="supervisor_tick",
            allowed=False,
            reason_code="ACTOR_FORBIDDEN",
            reason_text="actor_forbidden",
            chain_id=chain_id,
        )
        return {
            "ok": False,
            "ran": False,
            "error": "actor_forbidden",
            "policy_hit": "supervisor_tick",
            "chain_id": chain_id,
            "maintenance": maintenance,
        }

    cur = execution_window.current_window()
    window_open = bool(cur.get("open"))
    window_id = str(cur.get("window_id") or "")
    if not window_open:
        _journal(
            actor=clean_actor,
            reason=clean_reason,
            policy_hit="queue_blocked_window",
            allowed=False,
            reason_code="BLOCKED_WINDOW",
            reason_text="window_closed",
            chain_id=chain_id,
            window_id=window_id,
            extra={"window_open": False},
        )
        return {
            "ok": True,
            "ran": False,
            "blocked": "window_closed",
            "policy_hit": "queue_blocked_window",
            "chain_id": chain_id,
            "window": cur,
            "maintenance": maintenance,
        }

    state = agent_queue.fold_state()
    selected = agent_queue.select_next(now_ts=now, state=state)
    if not bool(selected.get("found")):
        sel_reason = str(selected.get("reason") or "queue_empty")
        if sel_reason == "challenge_window":
            _journal(
                actor=clean_actor,
                reason=clean_reason,
                policy_hit="queue_blocked_challenge",
                allowed=False,
                reason_code="BLOCKED_CHALLENGE",
                reason_text="challenge_window",
                chain_id=chain_id,
                window_id=window_id,
                queue_id=str(selected.get("queue_id") or ""),
                extra={
                    "next_not_before_ts": int(selected.get("next_not_before_ts") or 0),
                    "wait_sec": int(selected.get("wait_sec") or 0),
                },
            )
            return {
                "ok": True,
                "ran": False,
                "blocked": "challenge_window",
                "policy_hit": "queue_blocked_challenge",
                "chain_id": chain_id,
                "window": cur,
                "select": selected,
                "maintenance": maintenance,
            }

        _journal(
            actor=clean_actor,
            reason=clean_reason,
            policy_hit="supervisor_tick",
            allowed=True,
            reason_code="IDLE_QUEUE_EMPTY",
            reason_text="queue_empty",
            chain_id=chain_id,
            window_id=window_id,
        )
        return {
            "ok": True,
            "ran": False,
            "idle": True,
            "policy_hit": "supervisor_tick",
            "chain_id": chain_id,
            "window": cur,
            "select": selected,
            "maintenance": maintenance,
        }

    candidate = dict(selected.get("candidate") or {})
    queue_id = str(candidate.get("queue_id") or "")
    agent_id = str(candidate.get("agent_id") or "").strip()
    requires_approval = bool(candidate.get("requires_approval"))
    approved = bool(candidate.get("approved"))
    if not queue_id:
        return {"ok": False, "ran": False, "error": "queue_id_missing", "chain_id": chain_id}

    if requires_approval and (not approved):
        _journal(
            actor=clean_actor,
            reason=clean_reason,
            policy_hit="queue_blocked_approval",
            allowed=False,
            reason_code="BLOCKED_APPROVAL",
            reason_text="approval_required",
            chain_id=chain_id,
            queue_id=queue_id,
            window_id=window_id,
            agent_id=agent_id,
            extra={
                "requires_approval": True,
                "approved": False,
            },
        )
        return {
            "ok": True,
            "ran": False,
            "executed": False,
            "blocked": "approval",
            "policy_hit": "queue_blocked_approval",
            "chain_id": chain_id,
            "window": cur,
            "candidate": candidate,
            "maintenance": maintenance,
        }

    if bool(dry_run):
        _journal(
            actor=clean_actor,
            reason=clean_reason,
            policy_hit="supervisor_tick",
            allowed=True,
            reason_code="DRY_RUN",
            reason_text="dry_run",
            chain_id=chain_id,
            queue_id=queue_id,
            window_id=window_id,
            agent_id=agent_id,
            extra={"candidate": candidate},
        )
        return {
            "ok": True,
            "ran": False,
            "dry_run": True,
            "would_run": True,
            "queue_id": queue_id,
            "agent_id": agent_id,
            "chain_id": chain_id,
            "window": cur,
            "candidate": candidate,
            "maintenance": maintenance,
        }

    claim_rep = agent_queue.claim(queue_id, actor=clean_actor, reason=clean_reason)
    if not bool(claim_rep.get("ok")):
        _journal(
            actor=clean_actor,
            reason=clean_reason,
            policy_hit="queue_claim",
            allowed=False,
            reason_code="CLAIM_FAILED",
            reason_text=str(claim_rep.get("error") or "claim_failed"),
            chain_id=chain_id,
            queue_id=queue_id,
            window_id=window_id,
            agent_id=agent_id,
            extra={"claim": claim_rep},
        )
        return {
            "ok": False,
            "ran": False,
            "error": "claim_failed",
            "chain_id": chain_id,
            "queue_id": queue_id,
            "claim": claim_rep,
        }

    _journal(
        actor=clean_actor,
        reason=clean_reason,
        policy_hit="queue_claim",
        allowed=True,
        reason_code="CLAIMED",
        reason_text="queue_claimed",
        chain_id=chain_id,
        queue_id=queue_id,
        window_id=window_id,
        agent_id=agent_id,
    )

    plan_rep = agent_queue.load_plan(candidate)
    if not bool(plan_rep.get("ok")):
        fail_rep = agent_queue.fail(
            queue_id,
            actor=clean_actor,
            reason="plan_load_failed",
            error=str(plan_rep.get("error") or "plan_load_failed"),
            extra={"plan": plan_rep},
        )
        return {
            "ok": False,
            "ran": False,
            "error": "plan_load_failed",
            "chain_id": chain_id,
            "queue_id": queue_id,
            "plan": plan_rep,
            "fail": fail_rep,
        }

    if not agent_id:
        fail_rep = agent_queue.fail(
            queue_id,
            actor=clean_actor,
            reason="agent_id_required",
            error="agent_id_required",
        )
        return {
            "ok": False,
            "ran": False,
            "error": "agent_id_required",
            "chain_id": chain_id,
            "queue_id": queue_id,
            "fail": fail_rep,
        }

    run_id = "run_sup_" + uuid.uuid4().hex[:12]
    start_rep = agent_queue.start(
        queue_id,
        actor=clean_actor,
        reason=clean_reason,
        run_id=run_id,
        agent_id=agent_id,
    )
    if not bool(start_rep.get("ok")):
        return {
            "ok": False,
            "ran": False,
            "error": "queue_start_failed",
            "chain_id": chain_id,
            "queue_id": queue_id,
            "start": start_rep,
        }

    _journal(
        actor=clean_actor,
        reason=clean_reason,
        policy_hit="queue_start",
        allowed=True,
        reason_code="STARTED",
        reason_text="queue_started",
        chain_id=chain_id,
        queue_id=queue_id,
        window_id=window_id,
        agent_id=agent_id,
        run_id=run_id,
    )

    plan_payload = plan_rep.get("plan")
    run_ctx = {
        "intent": clean_reason,
        "chain_id": chain_id,
        "run_id": run_id,
    }
    try:
        run_rep = agent_runner.run_once(agent_id, plan_payload, ctx=run_ctx)
    except Exception as exc:
        run_rep = {"ok": False, "error": "run_once_exception", "detail": str(exc), "status": "failed"}

    elapsed_ms = int(max(0.0, (time.monotonic() - start_mon) * 1000.0))
    used_seconds = max(1, elapsed_ms // 1000)
    _ = execution_window.note_usage(window_id, used_seconds=used_seconds, used_energy=1)

    run_ok = bool(run_rep.get("ok"))
    run_status = str(run_rep.get("status") or "")
    if run_ok and run_status == "done":
        done_rep = agent_queue.done(
            queue_id,
            actor=clean_actor,
            reason="run_done",
            run_id=str(run_rep.get("run_id") or run_id),
            extra={
                "status": run_status,
                "steps_done": int(run_rep.get("steps_done") or 0),
                "steps_total": int(run_rep.get("steps_total") or 0),
            },
        )
        _journal(
            actor=clean_actor,
            reason=clean_reason,
            policy_hit="supervisor_tick",
            allowed=True,
            reason_code="RUN_DONE",
            reason_text="run_done",
            chain_id=chain_id,
            queue_id=queue_id,
            window_id=window_id,
            agent_id=agent_id,
            run_id=str(run_rep.get("run_id") or run_id),
            extra={"done": done_rep},
            duration_ms=elapsed_ms,
        )
        return {
            "ok": True,
            "ran": True,
            "queue_id": queue_id,
            "agent_id": agent_id,
            "run_id": str(run_rep.get("run_id") or run_id),
            "window_id": window_id,
            "policy_hit": "supervisor_tick",
            "chain_id": chain_id,
            "result": run_rep,
            "maintenance": maintenance,
        }

    fail_reason = str(run_rep.get("error") or run_status or "run_failed")
    fail_rep = agent_queue.fail(
        queue_id,
        actor=clean_actor,
        reason="run_failed",
        run_id=str(run_rep.get("run_id") or run_id),
        error=fail_reason,
        extra={"result": run_rep},
    )
    _journal(
        actor=clean_actor,
        reason=clean_reason,
        policy_hit="supervisor_tick",
        allowed=False,
        reason_code="RUN_FAILED",
        reason_text=fail_reason,
        chain_id=chain_id,
        queue_id=queue_id,
        window_id=window_id,
        agent_id=agent_id,
        run_id=str(run_rep.get("run_id") or run_id),
        extra={"fail": fail_rep},
        duration_ms=elapsed_ms,
    )
    return {
        "ok": False,
        "ran": False,
        "error": "run_failed",
        "reason": fail_reason,
        "queue_id": queue_id,
        "agent_id": agent_id,
        "run_id": str(run_rep.get("run_id") or run_id),
        "window_id": window_id,
        "policy_hit": "supervisor_tick",
        "chain_id": chain_id,
        "result": run_rep,
        "maintenance": maintenance,
    }


__all__ = ["tick_once"]
