# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from modules.memory.facade import memory_add

_REG: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.RLock()
_TOKENS: Dict[str, Dict[str, Any]] = {}
_ENDPOINT: Optional[str] = None
_DEFAULT_TIMEOUT = 30
_BUILTINS_READY = False
_EXTRA_EXEC_ACTIONS = {
    "files.sandbox_write",
    "files.sha256_verify",
    "plan.build",
    "oracle.openai.call",
    "local.search",
    "local.extract",
    "local.crosscheck",
    "crystallize.fact",
    "crystallize.negative",
    "close.ticket",
    "web.search",
}


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _enqueue_journal(
    *,
    allowed: bool,
    reason_code: str,
    reason: str,
    agent_id: str,
    plan_hash: str,
    disallowed_actions: List[str],
    metadata: Dict[str, Any],
) -> None:
    try:
        from modules.volition import journal as volition_journal
    except Exception:
        return
    row = {
        "id": "vol_manual_" + uuid.uuid4().hex,
        "ts": int(time.time()),
        "chain_id": str(plan_hash or ("chain_enqueue_" + uuid.uuid4().hex[:10])),
        "step": "agent.queue.enqueue",
        "actor": "ester",
        "intent": "agent_queue_enqueue",
        "action_kind": "agent.queue.enqueue",
        "needs": ["agent.queue.enqueue"],
        "allowed": bool(allowed),
        "reason_code": str(reason_code or ("ALLOW" if allowed else "DENY")),
        "reason": str(reason or ""),
        "slot": _slot(),
        "metadata": {
            "policy_hit": "agent.queue.enqueue",
            "agent_id": str(agent_id or ""),
            "plan_hash": str(plan_hash or ""),
            "disallowed_actions": list(disallowed_actions or []),
            **dict(metadata or {}),
        },
        "agent_id": str(agent_id or ""),
        "action_id": "agent.queue.enqueue",
        "decision": ("allow" if allowed else "deny"),
        "policy_hit": "agent.queue.enqueue",
        "duration_ms": 0,
    }
    try:
        volition_journal.append(row)
    except Exception:
        return


def _plan_actions_for_enqueue(plan: Any, plan_path: str = "") -> Tuple[List[str], str]:
    from modules.agents import plan_schema

    if str(plan_path or "").strip():
        load = plan_schema.load_plan_from_path(str(plan_path))
        if not bool(load.get("ok")):
            return [], ""
        norm_plan = dict(load.get("plan") or {})
    else:
        src = plan
        if isinstance(src, list):
            src = {"steps": src}
        norm = plan_schema.normalize_plan(dict(src or {}))
        norm_plan = dict(norm.get("plan") or {})
    actions: List[str] = []
    for row in list(norm_plan.get("steps") or []):
        if not isinstance(row, dict):
            continue
        aid = str(row.get("action") or row.get("action_id") or "").strip()
        if aid and aid not in actions:
            actions.append(aid)
    ph = ""
    try:
        val = plan_schema.validate_plan(norm_plan, registry=__import__(__name__, fromlist=["*"]))
        ph = str(val.get("plan_hash") or "")
    except Exception:
        ph = ""
    return actions, ph


def set_endpoint(base_url: str) -> None:
    global _ENDPOINT
    _ENDPOINT = (base_url or "").strip() or None


def _http_call(kind: str, args: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    import urllib.error
    import urllib.request

    if not _ENDPOINT:
        return {"ok": False, "error": "no_endpoint", "kind": kind}

    path = kind.replace(".", "/").strip("/")
    url = _ENDPOINT.rstrip("/") + "/" + path
    try:
        if args:
            data = json.dumps(args).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=max(1, int(timeout))) as r:  # nosec B310
            raw = r.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return {"ok": True, "value": parsed}
        except Exception:
            return {"ok": True, "raw": raw}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"http:{exc.code}", "url": url}
    except Exception as exc:
        return {"ok": False, "error": f"net:{exc}", "url": url}


def _normalize_register_args(
    timeout_sec: Any,
    concurrency: Any,
    fn: Any,
) -> Tuple[int, int, Optional[Callable[[Dict[str, Any]], Dict[str, Any]]]]:
    t = timeout_sec
    c = concurrency
    f = fn

    if callable(c) and f is None:
        f = c
        if isinstance(t, (int, float)) and 0 < int(t) <= 3600:
            c = int(t)
            t = _DEFAULT_TIMEOUT
        else:
            c = 1
            t = _DEFAULT_TIMEOUT
    elif callable(t) and f is None:
        f = t
        t = _DEFAULT_TIMEOUT
        c = 1

    try:
        t_i = int(t)
    except Exception:
        t_i = _DEFAULT_TIMEOUT
    try:
        c_i = int(c)
    except Exception:
        c_i = 1

    return max(1, t_i), max(1, c_i), (f if callable(f) else None)


def register(
    kind: str,
    inputs: Dict[str, str],
    outputs: Dict[str, str],
    timeout_sec: int = _DEFAULT_TIMEOUT,
    concurrency: int = 1,
    fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> None:
    if not isinstance(inputs, dict) or not isinstance(outputs, dict):
        raise ValueError("inputs/outputs must be dict")

    t, c, f = _normalize_register_args(timeout_sec, concurrency, fn)
    spec = {
        "kind": str(kind),
        "inputs": dict(inputs),
        "outputs": dict(outputs),
        "timeout_sec": int(t),
        "concurrency": int(c),
        "fn": f,
        "_sem": threading.BoundedSemaphore(int(c)),
        "wip": 0,
        "calls": 0,
        "fails": 0,
        "last_ts": 0,
    }
    with _LOCK:
        _REG[str(kind)] = spec


def _action_memory_add_note(args: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(args or {})
    text = str(payload.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "text_required"}
    tags = [str(x) for x in list(payload.get("tags") or []) if str(x).strip()]
    source = str(payload.get("source") or "action_registry")
    kind = str(payload.get("kind") or "fact")
    meta = dict(payload.get("meta") or {})
    meta.setdefault("source", source)
    if tags:
        meta.setdefault("tags", tags)
    rec = None
    warning = ""
    fallback_path = ""
    try:
        rec = memory_add(kind, text, meta=meta)
    except Exception as exc:
        warning = f"memory_add_failed:{exc.__class__.__name__}"
        try:
            import os

            root = (os.getenv("PERSIST_DIR") or "").strip() or os.path.join(os.getcwd(), "data")
            fb = os.path.join(root, "memory", "fallback_notes.jsonl")
            os.makedirs(os.path.dirname(fb), exist_ok=True)
            line = {
                "ts": int(time.time()),
                "kind": str(kind),
                "text": text,
                "meta": meta,
                "warning": str(exc),
            }
            with open(fb, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
                f.flush()
            fallback_path = fb
        except Exception:
            pass
    return {
        "ok": True,
        "kind": "memory.add_note",
        "id": (rec or {}).get("id") if isinstance(rec, dict) else None,
        "stored": bool(rec is not None),
        "warning": warning,
        "fallback_path": fallback_path,
        "record": rec if isinstance(rec, dict) else {},
    }


def _action_initiative_mark_done(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.proactivity import state_store

    payload = dict(args or {})
    initiative_id = str(payload.get("initiative_id") or "").strip()
    status = str(payload.get("status") or "done")
    note = str(payload.get("note") or "")
    agent_id = str(payload.get("agent_id") or "")
    chain_id = str(payload.get("chain_id") or "")
    return state_store.mark_done(
        initiative_id,
        status=status,
        note=note,
        agent_id=agent_id,
        chain_id=chain_id,
    )


def _action_proactivity_queue_add(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.proactivity import state_store

    payload = dict(args or {})
    return state_store.queue_add(
        initiative_id=str(payload.get("initiative_id") or "") or None,
        title=str(payload.get("title") or "Synthetic initiative"),
        text=str(payload.get("text") or ""),
        priority=str(payload.get("priority") or "normal"),
        source=str(payload.get("source") or "action_registry"),
        meta=dict(payload.get("meta") or {}),
    )


def _action_messages_outbox_enqueue(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.companion import outbox

    payload = dict(args or {})
    return outbox.enqueue(
        kind=str(payload.get("kind") or "note"),
        text=str(payload.get("text") or ""),
        meta=dict(payload.get("meta") or {}),
        chain_id=str(payload.get("chain_id") or ""),
        related_action=str(payload.get("related_action") or ""),
    )


def _action_messages_telegram_send(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.channels import telegram_sender

    payload = dict(args or {})
    return telegram_sender.send(
        text=str(payload.get("text") or ""),
        chat_id=payload.get("chat_id"),
        window_id=str(payload.get("window_id") or ""),
        reason=str(payload.get("reason") or "action_registry"),
        dry_run=(None if ("dry_run" not in payload) else bool(payload.get("dry_run"))),
    )


def _action_plan_build(args: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(args or {})
    goal = str(payload.get("goal") or payload.get("text") or "").strip()
    if not goal:
        return {"ok": False, "error": "goal_required"}

    source = str(payload.get("source") or "action_registry.plan.build").strip() or "action_registry.plan.build"
    try:
        n_steps = int(payload.get("steps") or 3)
    except Exception:
        n_steps = 3
    n_steps = max(2, min(7, n_steps))

    constraints = [str(x).strip() for x in list(payload.get("constraints") or []) if str(x).strip()]
    if not constraints:
        constraints = [
            "offline-first",
            "small verified increments",
            "explicit checks before completion",
        ]

    base_steps = [
        {"title": "Clarify objective", "detail": f"Rewrite goal in measurable form: {goal}"},
        {"title": "Collect minimal context", "detail": "Use only required local files/modules for this task."},
        {"title": "Implement smallest viable change", "detail": "Prefer deterministic and reversible edits."},
        {"title": "Run offline checks", "detail": "Execute targeted checks and capture outputs."},
        {"title": "Summarize result", "detail": "Return PASS/FAIL with concrete blockers if any."},
    ]
    steps = base_steps[:n_steps]
    plan = {
        "goal": goal,
        "source": source,
        "constraints": constraints,
        "steps": steps,
        "created_ts": int(time.time()),
    }
    lines = [f"Goal: {goal}"]
    for idx, row in enumerate(steps, start=1):
        lines.append(f"{idx}. {row.get('title')}: {row.get('detail')}")
    summary = f"Plan with {len(steps)} steps prepared."
    return {
        "ok": True,
        "plan": plan,
        "plan_text": "\n".join(lines),
        "summary": summary,
    }


def _oracle_args_digest(args: Dict[str, Any]) -> str:
    src = dict(args or {})
    safe = {
        "prompt": str(src.get("prompt") or ""),
        "model": str(src.get("model") or ""),
        "max_tokens": int(src.get("max_tokens") or 0),
        "temperature": float(src.get("temperature") or 0.0),
        "purpose": str(src.get("purpose") or ""),
        "window_id": str(src.get("window_id") or ""),
        "actor": str(src.get("actor") or ""),
        "agent_id": str(src.get("agent_id") or ""),
        "plan_id": str(src.get("plan_id") or ""),
        "step_index": src.get("step_index"),
        "request_id": str(src.get("request_id") or ""),
    }
    encoded = json.dumps(safe, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _append_oracle_deny_volition(payload: Dict[str, Any], rep: Dict[str, Any]) -> None:
    try:
        from modules.volition import journal as volition_journal
    except Exception:
        return
    actor = str(payload.get("actor") or "ester")
    agent_id = str(payload.get("agent_id") or "")
    plan_id = str(payload.get("plan_id") or "")
    action_id = "llm.remote.call"
    args_digest = _oracle_args_digest(payload)
    step_index_raw = payload.get("step_index")
    try:
        step_index = int(step_index_raw) if step_index_raw is not None else None
    except Exception:
        step_index = None
    budgets_left = dict(rep.get("budgets_left") or {})
    budgets_snapshot = {
        "max_calls": int((rep.get("budgets") or {}).get("max_calls") or 0),
        "remaining_calls": int(budgets_left.get("remaining_calls") or 0),
        "token_left_in": int(budgets_left.get("token_left_in") or 0),
        "token_left_out": int(budgets_left.get("token_left_out") or 0),
        "ttl_remaining": int(budgets_left.get("ttl_remaining") or 0),
    }
    reason = str(rep.get("error") or "oracle_denied")
    policy_hit = str(rep.get("policy_hit") or "oracle_window")
    chain_id = plan_id or ("chain_oracle_deny_" + uuid.uuid4().hex[:10])
    row = {
        "id": "vol_manual_" + uuid.uuid4().hex,
        "ts": int(time.time()),
        "chain_id": chain_id,
        "step": "action",
        "actor": actor,
        "intent": str(payload.get("purpose") or "llm.remote.call"),
        "action_kind": action_id,
        "allowed": False,
        "reason_code": "DENY_ORACLE",
        "reason": reason,
        "slot": str(rep.get("slot") or ""),
        "metadata": {
            "agent_id": agent_id,
            "plan_id": plan_id,
            "step_index": step_index,
            "action_id": action_id,
            "args_digest": args_digest,
            "budgets_snapshot": budgets_snapshot,
            "policy_hit": policy_hit,
            "oracle_window": str(rep.get("window_id") or payload.get("window_id") or ""),
        },
        "agent_id": agent_id,
        "plan_id": plan_id,
        "step_index": step_index,
        "action_id": action_id,
        "args_digest": args_digest,
        "budgets_snapshot": budgets_snapshot,
        "decision": "deny",
        "policy_hit": policy_hit,
        "duration_ms": 0,
    }
    volition_journal.append(row)


def _action_llm_remote_call(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.llm import providers_openai_oracle
    from modules.runtime import oracle_window

    payload = dict(args or {})
    prompt = str(payload.get("prompt") or "")
    if not prompt:
        oracle_window.note_call(
            "",
            {
                "window_id": "",
                "call_id": "oc_" + uuid.uuid4().hex[:12],
                "actor": str(payload.get("actor") or "ester"),
                "agent_id": str(payload.get("agent_id") or ""),
                "plan_id": str(payload.get("plan_id") or ""),
                "step_index": payload.get("step_index"),
                "model": str(payload.get("model") or ""),
                "prompt_digest": "",
                "input_chars": 0,
                "est_tokens_in": 0,
                "max_tokens": int(payload.get("max_tokens") or 0),
                "ok": False,
                "latency_ms": 0,
                "tokens_out": 0,
                "error": "prompt_required",
                "policy_hit": "oracle_args",
            },
        )
        rep = {"ok": False, "error": "prompt_required", "policy_hit": "oracle_args"}
        _append_oracle_deny_volition(payload, rep)
        return rep
    purpose = str(payload.get("purpose") or "").strip()
    if not purpose:
        oracle_window.note_call(
            "",
            {
                "window_id": "",
                "call_id": "oc_" + uuid.uuid4().hex[:12],
                "actor": str(payload.get("actor") or "ester"),
                "agent_id": str(payload.get("agent_id") or ""),
                "plan_id": str(payload.get("plan_id") or ""),
                "step_index": payload.get("step_index"),
                "model": str(payload.get("model") or ""),
                "prompt_digest": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "input_chars": len(prompt),
                "est_tokens_in": max(1, (len(prompt) + 3) // 4),
                "max_tokens": int(payload.get("max_tokens") or 0),
                "ok": False,
                "latency_ms": 0,
                "tokens_out": 0,
                "error": "purpose_required",
                "policy_hit": "oracle_args",
            },
        )
        rep = {"ok": False, "error": "purpose_required", "policy_hit": "oracle_args"}
        _append_oracle_deny_volition(payload, rep)
        return rep

    rep = providers_openai_oracle.call(
        prompt=prompt,
        model=str(payload.get("model") or ""),
        timeout=int(payload.get("timeout") or 20),
        window_id=str(payload.get("window_id") or ""),
        reason=purpose,
        dry_run=(None if ("dry_run" not in payload) else bool(payload.get("dry_run"))),
        max_tokens=int(payload.get("max_tokens") or 256),
        temperature=float(payload.get("temperature") if payload.get("temperature") is not None else 0.2),
        purpose=purpose,
        actor=str(payload.get("actor") or "ester"),
        agent_id=str(payload.get("agent_id") or ""),
        plan_id=str(payload.get("plan_id") or ""),
        step_index=payload.get("step_index"),
        request_id=str(payload.get("request_id") or ""),
    )
    if not bool(rep.get("ok")) and str(rep.get("error") or "").startswith("oracle_"):
        _append_oracle_deny_volition(payload, rep if isinstance(rep, dict) else {})
    return rep if isinstance(rep, dict) else {"ok": False, "error": "oracle_call_invalid_reply"}


def _action_oracle_request(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.runtime import oracle_requests

    payload = dict(args or {})
    agent_id = str(payload.get("agent_id") or "").strip()
    if not agent_id:
        return {"ok": False, "error": "agent_id_required"}
    model = str(payload.get("model") or "gpt-4o-mini").strip()
    action_id = str(payload.get("action_id") or "llm.remote.call").strip() or "llm.remote.call"
    return oracle_requests.submit_request(
        agent_id=agent_id,
        plan_id=str(payload.get("plan_id") or ""),
        step_index=payload.get("step_index"),
        action_id=action_id,
        model=model,
        purpose=str(payload.get("purpose") or ""),
        prompt_digest=str(payload.get("prompt_digest") or payload.get("prompt_hash") or ""),
        budgets_requested=dict(payload.get("budgets_requested") or {}),
    )


def _action_oracle_approve(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.runtime import oracle_requests

    payload = dict(args or {})
    request_id = str(payload.get("request_id") or "").strip()
    if not request_id:
        return {"ok": False, "error": "request_id_required"}
    actor = str(payload.get("actor") or "ester").strip() or "ester"
    return oracle_requests.approve_request(
        request_id,
        actor=actor,
        reason=str(payload.get("reason") or ""),
        ttl_sec=(None if payload.get("ttl_sec") is None else int(payload.get("ttl_sec"))),
        budgets=dict(payload.get("budgets") or {}),
        allow_agents=bool(payload.get("allow_agents", True)),
    )


def _action_oracle_deny(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.runtime import oracle_requests

    payload = dict(args or {})
    request_id = str(payload.get("request_id") or "").strip()
    if not request_id:
        return {"ok": False, "error": "request_id_required"}
    actor = str(payload.get("actor") or "ester").strip() or "ester"
    return oracle_requests.deny_request(
        request_id,
        actor=actor,
        reason=str(payload.get("reason") or "denied_by_ester"),
    )


def _action_agent_resume(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.garage import agent_runner
    from modules.volition.volition_gate import VolitionContext, get_default_gate

    payload = dict(args or {})
    agent_id = str(payload.get("agent_id") or "").strip()
    if not agent_id:
        return {"ok": False, "error": "agent_id_required", "resumed": False}

    actor = str(payload.get("actor") or "ester:core").strip() or "ester:core"
    actor_low = actor.lower()
    if not (actor_low == "ester" or actor_low.startswith("ester:")):
        st = agent_runner.load_state(agent_id)
        return {
            "ok": False,
            "error": "actor_forbidden",
            "resumed": False,
            "agent_id": agent_id,
            "status": str(st.get("status") or "idle"),
            "run_id": str(st.get("current_run_id") or ""),
            "next_step_index": int(st.get("next_step_index") or 0),
        }

    st = agent_runner.load_state(agent_id)
    chain_id = str(payload.get("chain_id") or st.get("plan_id") or ("chain_agent_resume_" + uuid.uuid4().hex[:10]))
    reason = str(payload.get("reason") or "agent_resume")
    budgets = {
        "max_actions": 1,
        "max_work_ms": 2000,
        "window": 60,
        "est_work_ms": 150,
    }
    gate = get_default_gate()
    decision = gate.decide(
        VolitionContext(
            chain_id=chain_id,
            step="action",
            actor="ester",
            intent=reason,
            action_kind="agent.resume",
            needs=["agents.run"],
            budgets=budgets,
            metadata={
                "agent_id": agent_id,
                "plan_id": str(st.get("plan_id") or ""),
                "step_index": int(st.get("next_step_index") or 0),
                "action_id": "agent.resume",
                "policy_hit": "agent_resume",
            },
        )
    )
    if not decision.allowed:
        return {
            "ok": False,
            "error": "volition_denied",
            "resumed": False,
            "reason_code": decision.reason_code,
            "reason": decision.reason,
            "slot": decision.slot,
            "agent_id": agent_id,
            "status": str(st.get("status") or "idle"),
            "run_id": str(st.get("current_run_id") or ""),
            "next_step_index": int(st.get("next_step_index") or 0),
            "volition": decision.to_dict(),
        }

    dry_run = bool(payload.get("dry_run"))
    if dry_run:
        return {
            "ok": True,
            "resumed": False,
            "dry_run": True,
            "agent_id": agent_id,
            "status": str(st.get("status") or "idle"),
            "run_id": str(st.get("current_run_id") or ""),
            "next_step_index": int(st.get("next_step_index") or 0),
            "can_resume": bool(agent_runner.can_resume(agent_id, st)),
            "volition": decision.to_dict(),
        }

    rep = agent_runner.resume_run(
        agent_id,
        actor=actor,
        reason=reason,
        dry_run=False,
    )
    out = dict(rep if isinstance(rep, dict) else {"ok": False, "error": "resume_invalid_reply", "resumed": False})
    out.setdefault("agent_id", agent_id)
    out.setdefault("status", str(st.get("status") or "idle"))
    out.setdefault("run_id", str(st.get("current_run_id") or ""))
    out.setdefault("next_step_index", int(st.get("next_step_index") or 0))
    out.setdefault("resumed", bool(out.get("ok")))
    out["volition"] = decision.to_dict()
    return out


def _action_agent_queue_enqueue(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.garage import agent_factory, agent_queue

    payload = dict(args or {})
    plan = payload.get("plan")
    plan_path = str(payload.get("plan_path") or "").strip()
    if plan is None and not plan_path:
        return {"ok": False, "error": "plan_required"}
    slot = _slot()
    strict = bool(slot == "B")
    agent_id = str(payload.get("agent_id") or "").strip()
    quarantine_warning = ""
    integrity_warning = ""
    quarantine_ctx: Dict[str, Any] = {}
    drift_quarantine = None

    if not agent_id:
        if strict:
            _enqueue_journal(
                allowed=False,
                reason_code="AGENT_ID_REQUIRED",
                reason="agent_id_required",
                agent_id="",
                plan_hash="",
                disallowed_actions=[],
                metadata={},
            )
            return {"ok": False, "error": "agent_id_required", "error_code": "AGENT_ID_REQUIRED"}
    elif agent_id:
        try:
            from modules.runtime import drift_quarantine as drift_quarantine  # type: ignore
        except Exception:
            drift_quarantine = None
        if drift_quarantine is not None:
            q = drift_quarantine.ensure_quarantine_for_agent(agent_id, source="agent.queue.enqueue")
            quarantine_ctx = {
                "active": bool(q.get("active")),
                "event_id": str(q.get("event_id") or ""),
                "reason_code": str(q.get("reason_code") or ""),
                "severity": str(q.get("severity") or ""),
                "kind": str(q.get("kind") or ""),
                "enforced": bool(q.get("enforced")),
                "mode_forced": str(q.get("mode_forced") or ""),
            }
            if bool(q.get("active")) and bool(q.get("enforced")):
                _enqueue_journal(
                    allowed=False,
                    reason_code="DRIFT_QUARANTINED",
                    reason="drift quarantine active",
                    agent_id=agent_id,
                    plan_hash="",
                    disallowed_actions=[],
                    metadata={"quarantine": dict(quarantine_ctx)},
                )
                try:
                    drift_quarantine.note_quarantine_block(
                        agent_id,
                        str(q.get("event_id") or ""),
                        str(q.get("reason_code") or "DRIFT_QUARANTINED"),
                        str(q.get("severity") or "HIGH"),
                        step="agent.queue.enqueue",
                        details={"source": "action_registry", "kind": str(q.get("kind") or "")},
                    )
                except Exception:
                    pass
                return {
                    "ok": False,
                    "error": "drift_quarantined",
                    "error_code": "DRIFT_QUARANTINED",
                    "agent_id": agent_id,
                    "quarantine": quarantine_ctx,
                }
            if bool(q.get("active")) and (not bool(q.get("enforced"))):
                quarantine_warning = "drift_quarantine_active_observe_only"

    allowlist: List[str] = []
    auth_source = "legacy"
    if agent_id:
        rep = agent_factory.get_agent(agent_id)
        if not bool(rep.get("ok")):
            _enqueue_journal(
                allowed=False,
                reason_code="AGENT_NOT_FOUND",
                reason="agent_not_found",
                agent_id=agent_id,
                plan_hash="",
                disallowed_actions=[],
                metadata={},
            )
            return {"ok": False, "error": "agent_not_found", "error_code": "AGENT_NOT_FOUND", "agent_id": agent_id}
        spec = dict((rep.get("agent") or {}).get("spec") or {})
        spec_path = str((rep.get("agent") or {}).get("spec_path") or "").strip()
        try:
            from modules.runtime import integrity_verifier  # type: ignore
        except Exception:
            integrity_verifier = None  # type: ignore
        if integrity_verifier is not None and hasattr(integrity_verifier, "precheck_agent_action"):
            try:
                irep = integrity_verifier.precheck_agent_action(
                    agent_id,
                    template_id=str(spec.get("template_id") or ""),
                    spec_path=spec_path,
                    action="agent.queue.enqueue",
                )
            except Exception:
                irep = {"ok": True}
            if not bool(irep.get("ok")):
                qrep = dict(irep.get("quarantine") or {})
                meta = {
                    "integrity": dict(irep.get("integrity") or {}),
                    "spec_guard": dict(irep.get("spec_guard") or {}),
                }
                if qrep:
                    meta["quarantine"] = dict(qrep)
                _enqueue_journal(
                    allowed=False,
                    reason_code=str(irep.get("error_code") or "INTEGRITY_TAMPER"),
                    reason=str(irep.get("error") or "integrity_tamper"),
                    agent_id=agent_id,
                    plan_hash="",
                    disallowed_actions=[],
                    metadata=meta,
                )
                return {
                    "ok": False,
                    "error": str(irep.get("error") or "integrity_tamper"),
                    "error_code": str(irep.get("error_code") or "INTEGRITY_TAMPER"),
                    "reason_code": str(irep.get("reason_code") or ""),
                    "agent_id": agent_id,
                    "slot": str(irep.get("slot") or slot),
                    "enforced": bool(irep.get("enforced")),
                    "integrity": dict(irep.get("integrity") or {}),
                    "spec_guard": dict(irep.get("spec_guard") or {}),
                    "quarantine": dict(qrep),
                }
            if list(irep.get("warnings") or []):
                integrity_warning = str(list(irep.get("warnings") or [])[0] or "")
        allow_rep = agent_factory.resolve_allowlist_for_spec(spec, slot_override=slot)
        if not bool(allow_rep.get("ok")):
            if strict:
                _enqueue_journal(
                    allowed=False,
                    reason_code=str(allow_rep.get("error_code") or "AUTHORITY_INVALID"),
                    reason=str(allow_rep.get("error") or "authority_invalid"),
                    agent_id=agent_id,
                    plan_hash="",
                    disallowed_actions=[],
                    metadata={"details": dict(allow_rep.get("details") or {})},
                )
                return {
                    "ok": False,
                    "error": str(allow_rep.get("error") or "authority_invalid"),
                    "error_code": str(allow_rep.get("error_code") or "AUTHORITY_INVALID"),
                    "agent_id": agent_id,
                }
            allowlist = [str(x) for x in list(spec.get("allowed_actions") or []) if str(x).strip()]
            auth_source = "slot_a_legacy_fallback"
        else:
            allowlist = [str(x) for x in list(allow_rep.get("allowed_actions") or []) if str(x).strip()]
            auth_source = str(allow_rep.get("source") or "resolved")

    step_actions, plan_hash = _plan_actions_for_enqueue(plan, plan_path=plan_path)
    if allowlist and step_actions:
        disallowed = sorted({a for a in step_actions if a not in set(allowlist)})
        if disallowed:
            _enqueue_journal(
                allowed=False,
                reason_code="ACTION_NOT_ALLOWED",
                reason="disallowed action in plan",
                agent_id=agent_id,
                plan_hash=plan_hash,
                disallowed_actions=disallowed,
                metadata={"allowlist_source": auth_source},
            )
            return {
                "ok": False,
                "error": "action_not_allowed",
                "error_code": "ACTION_NOT_ALLOWED",
                "agent_id": agent_id,
                "plan_hash": plan_hash,
                "disallowed_actions": disallowed,
            }
    elif strict and agent_id and (not allowlist):
        _enqueue_journal(
            allowed=False,
            reason_code="ALLOWLIST_EMPTY",
            reason="allowlist_empty",
            agent_id=agent_id,
            plan_hash=plan_hash,
            disallowed_actions=[],
            metadata={"allowlist_source": auth_source},
        )
        return {
            "ok": False,
            "error": "allowlist_empty",
            "error_code": "ALLOWLIST_EMPTY",
            "agent_id": agent_id,
            "plan_hash": plan_hash,
        }

    _enqueue_journal(
        allowed=True,
        reason_code="ALLOW",
        reason="plan_actions_within_allowlist",
        agent_id=agent_id,
        plan_hash=plan_hash,
        disallowed_actions=[],
        metadata={
            "allowlist_source": auth_source,
            "actions_total": len(step_actions),
            "quarantine": dict(quarantine_ctx),
        },
    )
    requires_approval_raw = payload.get("requires_approval")
    requires_approval_opt = None
    if requires_approval_raw is not None:
        requires_approval_opt = str(requires_approval_raw).strip().lower() in {"1", "true", "yes", "on", "y"}
    priority_raw = payload.get("priority")
    challenge_raw = payload.get("challenge_sec")
    out = agent_queue.enqueue(
        plan,
        priority=(50 if priority_raw is None else int(priority_raw)),
        challenge_sec=(60 if challenge_raw is None else int(challenge_raw)),
        not_before_ts=(None if payload.get("not_before_ts") is None else int(payload.get("not_before_ts"))),
        actor=str(payload.get("actor") or "ester"),
        reason=str(payload.get("reason") or ""),
        plan_path=plan_path,
        agent_id=agent_id,
        requires_approval=requires_approval_opt,
        queue_id=str(payload.get("queue_id") or ""),
    )
    if isinstance(out, dict):
        if quarantine_warning or integrity_warning:
            warnings = [str(x) for x in list(out.get("warnings") or []) if str(x).strip()]
            if quarantine_warning and quarantine_warning not in warnings:
                warnings.append(quarantine_warning)
            if integrity_warning and integrity_warning not in warnings:
                warnings.append(integrity_warning)
            out["warnings"] = warnings
        if quarantine_ctx:
            out["quarantine"] = dict(quarantine_ctx)
    return out


def _action_drift_quarantine_clear(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.runtime import drift_quarantine

    payload = dict(args or {})
    agent_id = str(payload.get("agent_id") or "").strip()
    event_id = str(payload.get("event_id") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    by = str(payload.get("by") or payload.get("actor") or "ester").strip() or "ester"
    chain_id = str(payload.get("chain_id") or ("chain_drift_quarantine_clear_" + uuid.uuid4().hex[:10])).strip()
    evidence = dict(payload.get("evidence") or {})
    evidence_note = str(payload.get("evidence_note") or "").strip()
    l4w = dict(payload.get("l4w") or {})

    if not agent_id:
        return {"ok": False, "error": "agent_id_required", "error_code": "AGENT_ID_REQUIRED"}
    if not event_id:
        return {"ok": False, "error": "event_id_required", "error_code": "EVENT_ID_REQUIRED"}
    if not reason:
        return {"ok": False, "error": "reason_required", "error_code": "REASON_REQUIRED"}

    rep = drift_quarantine.clear_quarantine(
        agent_id,
        event_id,
        chain_id,
        by,
        reason=reason,
        evidence=evidence,
        evidence_note=evidence_note,
        l4w=l4w,
    )
    out = dict(rep if isinstance(rep, dict) else {"ok": False, "error": "clear_invalid_reply"})
    out.setdefault("agent_id", agent_id)
    out.setdefault("event_id", event_id)
    out.setdefault("chain_id", chain_id)
    out.setdefault("evidence_sig_ok", bool(out.get("evidence_sig_ok")))
    out.setdefault("evidence_sig_alg", str(out.get("evidence_sig_alg") or ""))
    out.setdefault("evidence_sig_key_id", str(out.get("evidence_sig_key_id") or ""))
    out.setdefault("evidence_sig_error_code", str(out.get("evidence_sig_error_code") or ""))
    out.setdefault("evidence_payload_hash", str(out.get("evidence_payload_hash") or ""))
    out.setdefault("l4w_envelope_path", str(out.get("l4w_envelope_path") or ""))
    out.setdefault("l4w_envelope_sha256", str(out.get("l4w_envelope_sha256") or ""))
    out.setdefault("l4w_envelope_hash", str(out.get("l4w_envelope_hash") or ""))
    out.setdefault("l4w_prev_hash", str(out.get("l4w_prev_hash") or ""))
    out.setdefault("l4w_pub_fingerprint", str(out.get("l4w_pub_fingerprint") or ""))
    return out


def _action_agent_queue_list(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.garage import agent_queue

    payload = dict(args or {})
    return agent_queue.list_queue(live_only=bool(payload.get("live_only")))


def _action_agent_queue_cancel(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.garage import agent_queue

    payload = dict(args or {})
    queue_id = str(payload.get("queue_id") or "").strip()
    if not queue_id:
        return {"ok": False, "error": "queue_id_required"}
    return agent_queue.cancel(
        queue_id,
        actor=str(payload.get("actor") or "ester"),
        reason=str(payload.get("reason") or "cancelled_by_actor"),
    )


def _action_agent_queue_approve(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.garage import agent_queue

    payload = dict(args or {})
    queue_id = str(payload.get("queue_id") or "").strip()
    if not queue_id:
        return {"ok": False, "error": "queue_id_required"}
    rep = agent_queue.approve(
        queue_id,
        actor=str(payload.get("actor") or "ester"),
        reason=str(payload.get("reason") or "approved_by_actor"),
    )
    out = dict(rep if isinstance(rep, dict) else {"ok": False, "error": "approve_invalid_reply"})
    out.setdefault("queue_id", queue_id)
    out.setdefault("approved", bool(out.get("ok")))
    out.setdefault("approved_ts", int(out.get("approved_ts") or 0))
    return out


def _action_agent_supervisor_tick_once(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.garage import agent_supervisor

    payload = dict(args or {})
    return agent_supervisor.tick_once(
        actor=str(payload.get("actor") or "ester"),
        reason=str(payload.get("reason") or "action_registry_tick"),
        dry_run=bool(payload.get("dry_run")),
    )


def _action_execution_window_open(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.runtime import execution_window

    payload = dict(args or {})
    return execution_window.open_window(
        actor=str(payload.get("actor") or "ester"),
        reason=str(payload.get("reason") or ""),
        ttl_sec=(None if payload.get("ttl_sec") is None else int(payload.get("ttl_sec"))),
        budget_seconds=(None if payload.get("budget_seconds") is None else int(payload.get("budget_seconds"))),
        budget_energy=(None if payload.get("budget_energy") is None else int(payload.get("budget_energy"))),
        meta=dict(payload.get("meta") or {}),
    )


def _action_execution_window_close(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.runtime import execution_window

    payload = dict(args or {})
    window_id = str(payload.get("window_id") or "").strip()
    if not window_id:
        return {"ok": False, "error": "window_id_required"}
    return execution_window.close_window(
        window_id,
        actor=str(payload.get("actor") or "ester"),
        reason=str(payload.get("reason") or ""),
    )


def _action_execution_window_status(args: Dict[str, Any]) -> Dict[str, Any]:
    del args
    from modules.runtime import execution_window

    return execution_window.status()


def _action_local_search(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.curiosity import executor as curiosity_executor

    return curiosity_executor.action_local_search(dict(args or {}))


def _action_local_extract(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.curiosity import executor as curiosity_executor

    return curiosity_executor.action_local_extract(dict(args or {}))


def _action_local_crosscheck(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.curiosity import executor as curiosity_executor

    return curiosity_executor.action_local_crosscheck(dict(args or {}))


def _action_crystallize_fact(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.curiosity import executor as curiosity_executor

    return curiosity_executor.action_crystallize_fact(dict(args or {}))


def _action_crystallize_negative(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.curiosity import executor as curiosity_executor

    return curiosity_executor.action_crystallize_negative(dict(args or {}))


def _action_close_ticket(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.curiosity import executor as curiosity_executor

    return curiosity_executor.action_close_ticket(dict(args or {}))


def _action_web_search(args: Dict[str, Any]) -> Dict[str, Any]:
    from modules.curiosity import executor as curiosity_executor

    return curiosity_executor.action_web_search(dict(args or {}))


def _ensure_builtin_actions() -> None:
    global _BUILTINS_READY
    with _LOCK:
        if _BUILTINS_READY:
            return
        _BUILTINS_READY = True
    register(
        "memory.add_note",
        {"text": "str", "tags": "list[str]", "source": "str"},
        {"ok": "bool", "id": "str"},
        10,
        1,
        _action_memory_add_note,
    )
    register(
        "initiative.mark_done",
        {"initiative_id": "str", "status": "str", "note": "str"},
        {"ok": "bool", "updated": "bool"},
        10,
        1,
        _action_initiative_mark_done,
    )
    register(
        "proactivity.queue.add",
        {"title": "str", "text": "str", "priority": "str"},
        {"ok": "bool", "initiative_id": "str"},
        10,
        1,
        _action_proactivity_queue_add,
    )
    register(
        "messages.outbox.enqueue",
        {"kind": "str", "text": "str", "meta": "dict"},
        {"ok": "bool", "msg_id": "str"},
        10,
        1,
        _action_messages_outbox_enqueue,
    )
    register(
        "messages.telegram.send",
        {"text": "str", "chat_id": "str", "window_id": "str", "reason": "str"},
        {"ok": "bool"},
        20,
        1,
        _action_messages_telegram_send,
    )
    register(
        "plan.build",
        {"goal": "str", "text": "str", "steps": "int", "constraints": "list[str]", "source": "str"},
        {"ok": "bool", "plan": "dict", "plan_text": "str", "summary": "str"},
        10,
        1,
        _action_plan_build,
    )
    register(
        "llm.remote.call",
        {
            "prompt": "str",
            "model": "str",
            "max_tokens": "int",
            "temperature": "float",
            "purpose": "str",
            "window_id": "str",
        },
        {"ok": "bool", "text": "str", "usage": "dict"},
        30,
        1,
        _action_llm_remote_call,
    )
    register(
        "oracle.request",
        {
            "agent_id": "str",
            "plan_id": "str",
            "step_index": "int",
            "action_id": "str",
            "model": "str",
            "purpose": "str",
            "prompt_digest": "str",
            "budgets_requested": "dict",
        },
        {"ok": "bool", "request_id": "str", "status": "str"},
        10,
        1,
        _action_oracle_request,
    )
    register(
        "oracle.approve",
        {"request_id": "str", "reason": "str", "ttl_sec": "int", "budgets": "dict", "allow_agents": "bool"},
        {"ok": "bool", "window_id": "str"},
        10,
        1,
        _action_oracle_approve,
    )
    register(
        "oracle.deny",
        {"request_id": "str", "reason": "str"},
        {"ok": "bool", "request_id": "str"},
        10,
        1,
        _action_oracle_deny,
    )
    register(
        "agent.resume",
        {"agent_id": "str", "reason": "str", "dry_run": "bool"},
        {"ok": "bool", "resumed": "bool", "status": "str", "run_id": "str", "next_step_index": "int"},
        20,
        1,
        _action_agent_resume,
    )
    register(
        "drift.quarantine.clear",
        {
            "agent_id": "str",
            "event_id": "str",
            "reason": "str",
            "by": "str",
            "chain_id": "str",
            "evidence": "dict",
            "evidence_note": "str",
            "l4w": "dict",
        },
        {"ok": "bool", "cleared": "bool", "agent_id": "str", "event_id": "str"},
        10,
        1,
        _action_drift_quarantine_clear,
    )
    register(
        "agent.queue.enqueue",
        {
            "plan": "any",
            "plan_path": "str",
            "priority": "int",
            "challenge_sec": "int",
            "not_before_ts": "int",
            "agent_id": "str",
            "actor": "str",
            "reason": "str",
            "requires_approval": "bool",
        },
        {"ok": "bool", "queue_id": "str", "not_before_ts": "int", "requires_approval": "bool", "approved": "bool"},
        10,
        1,
        _action_agent_queue_enqueue,
    )
    register(
        "agent.queue.list",
        {"live_only": "bool"},
        {"ok": "bool", "count": "int", "items": "list"},
        10,
        1,
        _action_agent_queue_list,
    )
    register(
        "agent.queue.cancel",
        {"queue_id": "str", "actor": "str", "reason": "str"},
        {"ok": "bool", "event": "dict"},
        10,
        1,
        _action_agent_queue_cancel,
    )
    register(
        "agent.queue.approve",
        {"queue_id": "str", "actor": "str", "reason": "str"},
        {"ok": "bool", "queue_id": "str", "approved": "bool", "approved_ts": "int"},
        10,
        1,
        _action_agent_queue_approve,
    )
    register(
        "agent.supervisor.tick_once",
        {"actor": "str", "reason": "str", "dry_run": "bool"},
        {"ok": "bool", "ran": "bool"},
        20,
        1,
        _action_agent_supervisor_tick_once,
    )
    register(
        "local.search",
        {
            "ticket_id": "str",
            "query": "str",
            "max_docs": "int",
            "max_depth": "int",
            "max_hops": "int",
            "source": "str",
        },
        {"ok": "bool", "hits_total": "int", "evidence": "dict"},
        20,
        1,
        _action_local_search,
    )
    register(
        "local.extract",
        {"ticket_id": "str", "query": "str", "top_k": "int"},
        {"ok": "bool", "candidates_total": "int", "evidence": "dict"},
        20,
        1,
        _action_local_extract,
    )
    register(
        "local.crosscheck",
        {"ticket_id": "str", "query": "str", "min_sources": "int"},
        {"ok": "bool", "crosscheck_ok": "bool", "sources_total": "int", "evidence": "dict"},
        20,
        1,
        _action_local_crosscheck,
    )
    register(
        "crystallize.fact",
        {"ticket_id": "str", "query": "str", "source": "str"},
        {"ok": "bool", "kind": "str", "summary": "str", "evidence_ref": "dict", "l4w": "dict"},
        20,
        1,
        _action_crystallize_fact,
    )
    register(
        "crystallize.negative",
        {"ticket_id": "str", "query": "str", "summary": "str"},
        {"ok": "bool", "kind": "str", "summary": "str", "evidence_ref": "dict", "l4w": "dict"},
        20,
        1,
        _action_crystallize_negative,
    )
    register(
        "close.ticket",
        {"ticket_id": "str", "default_event": "str"},
        {"ok": "bool", "ticket_id": "str", "event": "str"},
        10,
        1,
        _action_close_ticket,
    )
    register(
        "web.search",
        {"ticket_id": "str", "query": "str", "domains": "list"},
        {"ok": "bool", "chars": "int", "evidence": "dict"},
        30,
        1,
        _action_web_search,
    )
    register(
        "execution_window.open",
        {
            "actor": "str",
            "reason": "str",
            "ttl_sec": "int",
            "budget_seconds": "int",
            "budget_energy": "int",
            "meta": "dict",
        },
        {"ok": "bool", "window_id": "str"},
        10,
        1,
        _action_execution_window_open,
    )
    register(
        "execution_window.close",
        {"window_id": "str", "actor": "str", "reason": "str"},
        {"ok": "bool", "window_id": "str"},
        10,
        1,
        _action_execution_window_close,
    )
    register(
        "execution_window.status",
        {},
        {"ok": "bool", "open": "bool", "window_id": "str"},
        5,
        1,
        _action_execution_window_status,
    )


def invoke(kind: str, args: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_builtin_actions()
    with _LOCK:
        spec = _REG.get(str(kind))
    if not spec:
        return {"ok": False, "error": "unknown_action", "kind": str(kind)}

    sem: threading.BoundedSemaphore = spec["_sem"]  # type: ignore[assignment]
    if not sem.acquire(blocking=False):
        return {
            "ok": False,
            "error": "busy",
            "kind": str(kind),
            "concurrency": int(spec.get("concurrency") or 1),
        }

    try:
        spec["wip"] = int(spec.get("wip") or 0) + 1
        spec["calls"] = int(spec.get("calls") or 0) + 1
        spec["last_ts"] = int(time.time())
        timeout = int(spec.get("timeout_sec") or _DEFAULT_TIMEOUT)
        fn = spec.get("fn")
        if callable(fn):
            rep = fn(dict(args or {}))
            if isinstance(rep, dict):
                return rep
            return {"ok": True, "result": rep}
        return _http_call(str(kind), dict(args or {}), timeout)
    except Exception as exc:
        spec["fails"] = int(spec.get("fails") or 0) + 1
        return {
            "ok": False,
            "error": f"exception:{exc.__class__.__name__}",
            "detail": str(exc),
            "kind": str(kind),
        }
    finally:
        spec["wip"] = max(0, int(spec.get("wip") or 0) - 1)
        sem.release()


def invoke_guarded(
    kind: str,
    args: Dict[str, Any],
    *,
    ctx: Any = None,
    gate: Any = None,
) -> Dict[str, Any]:
    try:
        from modules.volition.volition_gate import VolitionContext, get_default_gate

        if gate is None:
            gate = get_default_gate()

        if ctx is None:
            vctx = VolitionContext(
                chain_id="chain_" + uuid.uuid4().hex[:12],
                step="action",
                actor="ester",
                intent=f"invoke:{kind}",
                action_kind=str(kind),
                needs=[],
                budgets={},
                metadata={},
            )
        else:
            vctx = VolitionContext.from_any(ctx)
            if not vctx.action_kind:
                vctx.action_kind = str(kind)
            if not vctx.step:
                vctx.step = "action"

        if str(kind) == "llm.remote.call":
            md = dict(vctx.metadata or {})
            md.setdefault("action_id", "llm.remote.call")
            md.setdefault("oracle_window", str((args or {}).get("window_id") or ""))
            md.setdefault("policy_hit", "oracle_window")
            md.setdefault("args_digest", _oracle_args_digest(dict(args or {})))
            md.setdefault(
                "budgets_snapshot",
                {
                    "max_calls": int((vctx.budgets or {}).get("max_actions") or 0),
                    "remaining_calls": 0,
                    "token_left_in": 0,
                    "token_left_out": 0,
                    "ttl_remaining": int((vctx.budgets or {}).get("window") or 0),
                },
            )
            vctx.metadata = md

        if str(kind) == "drift.quarantine.clear":
            md = dict(vctx.metadata or {})
            ev = dict((args or {}).get("evidence") or {})
            l4w = dict((args or {}).get("l4w") or {})
            md.setdefault("action_id", "drift.quarantine.clear")
            md.setdefault("policy_hit", "drift.quarantine.clear")
            md.setdefault("agent_id", str((args or {}).get("agent_id") or ""))
            md.setdefault("reason", str((args or {}).get("reason") or ""))
            md.setdefault("evidence_ref", str(ev.get("path") or ""))
            md.setdefault("evidence_hash", str(ev.get("sha256") or ""))
            md.setdefault("l4w_ref", str(l4w.get("envelope_path") or ""))
            md.setdefault("l4w_hash", str(l4w.get("envelope_sha256") or ""))
            vctx.metadata = md

        decision = gate.decide(vctx)
        if not decision.allowed:
            return {
                "ok": False,
                "error": "volition_denied",
                "reason_code": decision.reason_code,
                "reason": decision.reason,
                "slot": decision.slot,
                "kind": str(kind),
            }
    except Exception as exc:
        return {
            "ok": False,
            "error": "volition_gate_error",
            "detail": str(exc),
            "kind": str(kind),
        }

    rep = invoke(kind, args or {})
    if isinstance(rep, dict):
        rep.setdefault("kind", str(kind))
        try:
            vol = decision.to_dict()
            if str(kind) == "drift.quarantine.clear":
                md = dict(vol.get("metadata") or {})
                md["evidence_sig_ok"] = bool(rep.get("evidence_sig_ok"))
                md["evidence_sig_alg"] = str(rep.get("evidence_sig_alg") or "")
                md["evidence_sig_key_id"] = str(rep.get("evidence_sig_key_id") or "")
                md["evidence_sig_error_code"] = str(rep.get("evidence_sig_error_code") or "")
                md["evidence_payload_hash"] = str(rep.get("evidence_payload_hash") or "")
                md["l4w_envelope_path"] = str(rep.get("l4w_envelope_path") or "")
                md["l4w_envelope_sha256"] = str(rep.get("l4w_envelope_sha256") or "")
                md["l4w_envelope_hash"] = str(rep.get("l4w_envelope_hash") or "")
                md["l4w_prev_hash"] = str(rep.get("l4w_prev_hash") or "")
                md["l4w_pub_fingerprint"] = str(rep.get("l4w_pub_fingerprint") or "")
                vol["metadata"] = md
            rep.setdefault("volition", vol)
        except Exception:
            pass
    return rep


def list_registered() -> Dict[str, Dict[str, Any]]:
    _ensure_builtin_actions()
    with _LOCK:
        out: Dict[str, Dict[str, Any]] = {}
        for name, spec in _REG.items():
            out[name] = {
                "inputs": spec.get("inputs"),
                "outputs": spec.get("outputs"),
                "timeout_sec": int(spec.get("timeout_sec") or _DEFAULT_TIMEOUT),
                "concurrency": int(spec.get("concurrency") or 1),
                "has_fn": bool(spec.get("fn")),
                "wip": int(spec.get("wip") or 0),
                "calls": int(spec.get("calls") or 0),
                "fails": int(spec.get("fails") or 0),
                "last_ts": int(spec.get("last_ts") or 0),
            }
        return out


def list_actions() -> List[Dict[str, Any]]:
    info = list_registered()
    out: List[Dict[str, Any]] = []
    for name in sorted(info.keys()):
        row = dict(info[name])
        row["name"] = name
        out.append(row)
    return out


def list_action_ids() -> List[str]:
    _ensure_builtin_actions()
    with _LOCK:
        out = {str(name) for name in _REG.keys() if str(name).strip()}
    out.update(_EXTRA_EXEC_ACTIONS)
    return sorted(out)


def has_action(action_id: str) -> bool:
    aid = str(action_id or "").strip()
    if not aid:
        return False
    _ensure_builtin_actions()
    with _LOCK:
        if aid in _REG:
            return True
    return aid in _EXTRA_EXEC_ACTIONS


def status() -> Dict[str, Any]:
    _ensure_builtin_actions()
    return {
        "ok": True,
        "count": len(_REG),
        "endpoint": _ENDPOINT,
        "actions": list_actions(),
    }


def run(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_builtin_actions()
    return invoke(str(name), dict(args or {}))


def begin(name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    token = "act_" + uuid.uuid4().hex
    row = {
        "token": token,
        "name": str(name),
        "args": dict(args or {}),
        "ts": int(time.time()),
    }
    with _LOCK:
        _TOKENS[token] = row
    return {"ok": True, **row}


def finish(token: str, ok: bool = True, result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with _LOCK:
        row = _TOKENS.pop(str(token), None)
    return {
        "ok": True,
        "token": str(token),
        "known": bool(row),
        "action_ok": bool(ok),
        "result": dict(result or {}),
        "finished_ts": int(time.time()),
    }


__all__ = [
    "set_endpoint",
    "register",
    "invoke",
    "invoke_guarded",
    "list_registered",
    "list_actions",
    "list_action_ids",
    "has_action",
    "status",
    "run",
    "begin",
    "finish",
]
