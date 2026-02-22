# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from modules.garage import agent_factory, agent_queue
from modules.proactivity import planner_v1, template_bridge
from modules.thinking.action_registry import invoke_guarded
from modules.volition import journal as volition_journal
from modules.volition.volition_gate import VolitionContext, get_default_gate

try:
    from modules.proactivity import agent_create_approval
except Exception:
    agent_create_approval = None  # type: ignore

_SLOTB_ERR_STREAK = 0
_SLOTB_DISABLED = False


def _now_iso(ts: Optional[float] = None) -> str:
    value = float(ts if ts is not None else time.time())
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _slot_b_fail_max() -> int:
    try:
        return max(1, int(os.getenv("ESTER_PROACTIVITY_SLOTB_FAIL_MAX", "3") or "3"))
    except Exception:
        return 3


def _enqueue_enabled() -> bool:
    env_primary = _truthy(os.getenv("ESTER_PROACTIVITY_ENQUEUE_ENABLED", "1"))
    env_compat = _truthy(os.getenv("ESTER_PROACTIVITY_REAL_ACTIONS_ENABLED", "1"))
    return bool(env_primary and env_compat)


def _agent_create_requires_approval() -> bool:
    return _truthy(os.getenv("ESTER_AGENT_CREATE_REQUIRE_APPROVAL", "0"))


def _as_int(value: Any, default: int, *, min_value: int = 0) -> int:
    try:
        out = int(value)
    except Exception:
        out = int(default)
    return max(min_value, out)


def _persist_dir(create: bool = True) -> Path:
    raw = str(os.getenv("PERSIST_DIR") or "").strip()
    if not raw:
        raw = str((Path.cwd() / "data").resolve())
    p = Path(raw).resolve()
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def _enqueue_log_path(create: bool = True) -> Path:
    p = (_persist_dir(create=create) / "proactivity" / "enqueue.jsonl").resolve()
    if create:
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.touch()
    return p


def _initiative_queue_path(create: bool = True) -> Path:
    p = (_persist_dir(create=create) / "initiatives" / "queue.jsonl").resolve()
    if create:
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.touch()
    return p


def _executor_state_path(create: bool = True) -> Path:
    p = (_persist_dir(create=create) / "proactivity" / "executor_state.json").resolve()
    if create:
        p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_executor_state() -> Dict[str, Any]:
    return {
        "processed_ids": [],
        "items": {},
        "runtime": {
            "last_tick": None,
            "last_ok": None,
            "last_action_kind": "",
            "last_denied_at": "",
            "last_error": "",
            "queue_size": 0,
            "last_initiative_id": "",
            "last_plan_id": "",
            "last_template_id": "",
            "last_agent_id": "",
            "mode": {"plan_only": True, "run_safe": False},
            "last_run_ts": None,
        },
    }


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


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(dict(row or {}), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _load_executor_state_no_touch() -> Dict[str, Any]:
    p = _executor_state_path(create=False)
    if not p.exists():
        return _default_executor_state()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("bad_state")
    except Exception:
        raw = _default_executor_state()

    out = _default_executor_state()
    out.update(raw)
    vals = list(out.get("processed_ids") or [])
    out["processed_ids"] = [str(x) for x in vals if str(x).strip()]
    if not isinstance(out.get("items"), dict):
        out["items"] = {}
    rt = dict(out.get("runtime") or {})
    base_rt = dict(_default_executor_state().get("runtime") or {})
    base_rt.update(rt)
    if not isinstance(base_rt.get("mode"), dict):
        base_rt["mode"] = {"plan_only": True, "run_safe": False}
    out["runtime"] = base_rt
    return out


def _save_executor_state(state: Dict[str, Any]) -> None:
    p = _executor_state_path(create=True)
    payload = json.dumps(dict(state or {}), ensure_ascii=False, indent=2)
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(p)
        return
    except Exception:
        pass
    p.write_text(payload, encoding="utf-8")


def _read_processed_ids_no_touch() -> List[str]:
    st = _load_executor_state_no_touch()
    vals = list(st.get("processed_ids") or [])
    return [str(x) for x in vals if str(x).strip()]


def _read_initiative_queue_no_touch() -> List[Dict[str, Any]]:
    return _read_jsonl(_initiative_queue_path(create=False))


def _select_initiative(dry: bool) -> Optional[Dict[str, Any]]:
    del dry
    processed = set(_read_processed_ids_no_touch())
    rows = _read_initiative_queue_no_touch()
    for row in rows:
        iid = str(row.get("id") or "").strip()
        if iid and iid not in processed:
            return dict(row)
    return None


def _mark_processed(
    *,
    dry: bool,
    initiative_id: str,
    status: str,
    note: str,
    agent_id: str,
    chain_id: str,
) -> Dict[str, Any]:
    if dry:
        return {"ok": True, "dry_run": True}
    st = _load_executor_state_no_touch()
    processed = [str(x) for x in list(st.get("processed_ids") or []) if str(x).strip()]
    if initiative_id and initiative_id not in processed:
        processed.append(initiative_id)
    if len(processed) > 10000:
        processed = processed[-10000:]
    st["processed_ids"] = processed
    items = dict(st.get("items") or {})
    items[str(initiative_id)] = {
        "status": str(status or "planned"),
        "note": str(note or ""),
        "agent_id": str(agent_id or ""),
        "chain_id": str(chain_id or ""),
        "updated_ts": int(time.time()),
    }
    st["items"] = items
    _save_executor_state(st)
    return {"ok": True, "initiative_id": initiative_id, "status": status}


def _default_budgets(max_work_ms: Optional[int] = None) -> Dict[str, Any]:
    max_ms = _as_int(
        (max_work_ms if max_work_ms is not None else os.getenv("ESTER_PROACTIVITY_MAX_WORK_MS", "2000")),
        2000,
        min_value=200,
    )
    max_actions = _as_int(os.getenv("ESTER_PROACTIVITY_MAX_ACTIONS", "6"), 6, min_value=1)
    window = _as_int(os.getenv("ESTER_PROACTIVITY_WINDOW_SEC", os.getenv("ESTER_VOLITION_WINDOW_SEC", "60")), 60, min_value=1)
    est_work_ms = min(max_ms, _as_int(os.getenv("ESTER_PROACTIVITY_EST_WORK_MS", "250"), 250, min_value=1))
    return {
        "max_work_ms": max_ms,
        "max_actions": max_actions,
        "window": window,
        "est_work_ms": est_work_ms,
    }


def _normalize_mode(mode: str) -> str:
    m = str(mode or "enqueue").strip().lower()
    return "plan_only" if m == "plan_only" else "enqueue"


def _queue_size() -> int:
    try:
        st = agent_queue.fold_state()
        return max(0, int(st.get("live_total") or 0))
    except Exception:
        return 0


def _queue_last_enqueue_id() -> str:
    try:
        evs = agent_queue.events()
    except Exception:
        return ""
    for row in reversed(evs):
        if str(row.get("type") or "") == "enqueue":
            return str(row.get("queue_id") or "")
    return ""


def _extract_step_action_id(step: Dict[str, Any]) -> str:
    return str(step.get("action_id") or step.get("action") or "").strip()


def _normalize_plan_for_queue(plan: Dict[str, Any], *, initiative_id: str, template_id: str) -> Dict[str, Any]:
    src = dict(plan or {})
    steps_out: List[Dict[str, Any]] = []
    for raw in list(src.get("steps") or []):
        if not isinstance(raw, dict):
            continue
        action_id = _extract_step_action_id(raw)
        if not action_id:
            continue
        row: Dict[str, Any] = {
            "action_id": action_id,
            "args": dict(raw.get("args") or {}),
        }
        if isinstance(raw.get("budgets"), dict):
            row["budgets"] = dict(raw.get("budgets") or {})
        elif raw.get("budget_ms") is not None:
            row["budgets"] = {"max_work_ms": _as_int(raw.get("budget_ms"), 200, min_value=1)}
        steps_out.append(row)

    return {
        "schema": "ester.plan.v1",
        "plan_id": str(src.get("plan_id") or ("plan_" + uuid.uuid4().hex[:10])),
        "initiative_id": initiative_id,
        "title": str(src.get("title") or "initiative"),
        "template_id": template_id,
        "steps": steps_out,
        "budgets": dict(src.get("budgets") or {}),
        "meta": {"needs_oracle": bool(src.get("needs_oracle"))},
    }


def _plan_hash(plan: Dict[str, Any]) -> str:
    encoded = json.dumps(plan, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dedupe_hit(initiative_id: str, plan_hash: str, cooldown_sec: int) -> Dict[str, Any]:
    if cooldown_sec <= 0:
        return {"hit": False}
    now = int(time.time())
    rows = _read_jsonl(_enqueue_log_path(create=False))
    for row in reversed(rows):
        ts = _as_int(row.get("ts"), 0, min_value=0)
        if ts <= 0:
            continue
        if now - ts > cooldown_sec:
            break
        if str(row.get("initiative_id") or "") != initiative_id:
            continue
        if str(row.get("plan_hash") or "") != plan_hash:
            continue
        if not bool(row.get("ok")):
            continue
        return {
            "hit": True,
            "ts": ts,
            "enqueue_id": str(row.get("enqueue_id") or ""),
        }
    return {"hit": False}


def _extract_allowed_actions(template: Dict[str, Any], queue_plan: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for raw in list(template.get("allowed_actions") or []):
        s = str(raw or "").strip()
        if s and s not in out:
            out.append(s)
    for row in list(queue_plan.get("steps") or []):
        if not isinstance(row, dict):
            continue
        s = str(row.get("action_id") or "").strip()
        if s and s not in out:
            out.append(s)
    if not out:
        out = ["memory.add_note", "messages.outbox.enqueue", "proactivity.queue.add", "initiative.mark_done", "files.sandbox_write"]
    return out


def _find_agent_id_by_name(name: str) -> str:
    target = str(name or "").strip()
    if not target:
        return ""
    try:
        listing = agent_factory.list_agents()
    except Exception:
        return ""
    for row in list(listing.get("agents") or []):
        if str((row or {}).get("name") or "").strip() != target:
            continue
        if bool((row or {}).get("enabled", True)) is False:
            continue
        aid = str((row or {}).get("agent_id") or (row or {}).get("id") or "").strip()
        if aid:
            return aid
    return ""


def _ensure_default_agent(
    *,
    dry: bool,
    title: str,
    template: Dict[str, Any],
    queue_plan: Dict[str, Any],
    budgets: Dict[str, Any],
) -> Dict[str, Any]:
    default_name = "proactivity.enqueue.default"
    template_id = str(template.get("template_id") or "initiator.v1")
    template_caps = [str(x) for x in list(template.get("capabilities") or []) if str(x).strip()]
    if dry:
        return {
            "ok": True,
            "agent_id": "agent_dry_proactivity",
            "created": False,
            "dry_run": True,
            "name": default_name,
            "template_id": template_id,
            "capabilities": template_caps,
        }

    listing = agent_factory.list_agents()
    for row in list(listing.get("agents") or []):
        if str(row.get("name") or "") == default_name:
            return {
                "ok": True,
                "agent_id": str(row.get("agent_id") or row.get("id") or ""),
                "created": False,
                "name": default_name,
            }

    allowed_actions = _extract_allowed_actions(template, queue_plan)
    create_rep = agent_factory.create_agent(
        {
            "name": default_name,
            "goal": str(title or "proactivity enqueue"),
            "template_id": template_id,
            "capabilities": list(template_caps),
            "allowed_actions": allowed_actions,
            "budgets": {
                "max_actions": max(4, int(budgets.get("max_actions") or 6)),
                "max_work_ms": max(1000, int(budgets.get("max_work_ms") or 2000)),
                "window": max(30, int(budgets.get("window") or 60)),
                "est_work_ms": max(100, int(budgets.get("est_work_ms") or 250)),
            },
            "owner": "modules.proactivity.executor",
            "oracle_policy": {"allow_remote": bool((queue_plan.get("meta") or {}).get("needs_oracle"))},
        }
    )
    if not bool(create_rep.get("ok")):
        return dict(create_rep)
    return {
        "ok": True,
        "agent_id": str(create_rep.get("agent_id") or ""),
        "created": True,
        "name": default_name,
        "spec": dict((create_rep.get("spec") or {})),
    }


def _append_enqueue_log(
    *,
    dry: bool,
    chain_id: str,
    initiative_id: str,
    plan_id: str,
    plan_hash: str,
    agent_id: str,
    enqueue_id: str,
    ok: bool,
    error: str,
) -> None:
    if dry:
        return
    row = {
        "ts": int(time.time()),
        "chain_id": str(chain_id or ""),
        "initiative_id": str(initiative_id or ""),
        "plan_id": str(plan_id or ""),
        "plan_hash": str(plan_hash or ""),
        "agent_id": str(agent_id or ""),
        "enqueue_id": str(enqueue_id or ""),
        "ok": bool(ok),
        "error": str(error or ""),
    }
    _append_jsonl(_enqueue_log_path(create=True), row)


def _update_runtime(
    *,
    dry: bool,
    mode: str,
    ok: bool,
    error: str,
    denied_at: str,
    action_kind: str,
    initiative_id: str,
    plan_id: str,
    template_id: str,
    agent_id: str,
) -> None:
    if dry:
        return
    st = _load_executor_state_no_touch()
    rt = dict(st.get("runtime") or {})
    rt["last_tick"] = _now_iso()
    rt["last_ok"] = bool(ok)
    rt["last_action_kind"] = str(action_kind or "")
    rt["last_denied_at"] = str(denied_at or "")
    rt["last_error"] = str(error or "")
    rt["queue_size"] = _queue_size()
    rt["last_initiative_id"] = str(initiative_id or "")
    rt["last_plan_id"] = str(plan_id or "")
    rt["last_template_id"] = str(template_id or "")
    rt["last_agent_id"] = str(agent_id or "")
    rt["mode"] = {"plan_only": bool(mode == "plan_only"), "run_safe": False}
    rt["last_run_ts"] = int(time.time())
    st["runtime"] = rt
    _save_executor_state(st)


def _gate_decide(
    *,
    gate: Any,
    chain_id: str,
    step: str,
    needs: List[str],
    actor: str,
    intent: str,
    budgets: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    decision = gate.decide(
        VolitionContext(
            chain_id=chain_id,
            step=str(step or "action"),
            actor=str(actor or "ester"),
            intent=str(intent or step or "proactivity"),
            action_kind=str(step or ""),
            needs=list(needs or []),
            budgets=dict(budgets or {}),
            metadata=dict(metadata or {}),
        )
    )
    rep = decision.to_dict()
    _append_manual_step_journal(
        chain_id=chain_id,
        step=step,
        actor=actor,
        intent=intent,
        needs=needs,
        budgets=budgets,
        decision=rep,
    )
    return rep


def _append_manual_step_journal(
    *,
    chain_id: str,
    step: str,
    actor: str,
    intent: str,
    needs: List[str],
    budgets: Dict[str, Any],
    decision: Dict[str, Any],
) -> None:
    allowed = bool(decision.get("allowed"))
    reason_code = str(decision.get("reason_code") or ("ALLOW" if allowed else "DENY"))
    reason = str(decision.get("reason") or "")
    slot = str(decision.get("slot") or _slot())
    row = {
        "id": "vol_manual_" + uuid.uuid4().hex,
        "ts": int(time.time()),
        "chain_id": str(chain_id or ""),
        "step": str(step or ""),
        "actor": str(actor or "ester"),
        "intent": str(intent or step or ""),
        "action_kind": str(step or ""),
        "allowed": allowed,
        "reason_code": reason_code,
        "reason": reason,
        "slot": slot,
        "metadata": {
            "needs": [str(x) for x in list(needs or []) if str(x).strip()],
            "budgets_snapshot": dict(budgets or {}),
            "policy_hit": str(step or ""),
        },
        "decision": ("allow" if allowed else "deny"),
        "policy_hit": str(step or ""),
        "duration_ms": int(decision.get("duration_ms") or 0),
    }
    try:
        volition_journal.append(row)
    except Exception:
        return


def _enqueue_via_action(
    *,
    gate: Any,
    chain_id: str,
    budgets: Dict[str, Any],
    actor: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    rep = invoke_guarded(
        "agent.queue.enqueue",
        dict(payload or {}),
        gate=gate,
        ctx=VolitionContext(
            chain_id=chain_id,
            step="agent.queue.enqueue",
            actor=str(actor or "ester"),
            intent="proactivity_enqueue",
            action_kind="agent.queue.enqueue",
            needs=["agent.queue.enqueue"],
            budgets=dict(budgets or {}),
            metadata={
                "initiative_id": str(payload.get("initiative_id") or ""),
                "plan_id": str(payload.get("plan_id") or ""),
                "agent_id": str(payload.get("agent_id") or ""),
                "reason": str(payload.get("reason") or ""),
            },
        ),
    )
    vol = dict(rep.get("volition") or {}) if isinstance(rep, dict) else {}
    _append_manual_step_journal(
        chain_id=chain_id,
        step="agent.queue.enqueue",
        actor=str(actor or "ester"),
        intent="proactivity_enqueue",
        needs=["agent.queue.enqueue"],
        budgets=budgets,
        decision=vol,
    )
    return rep


def _run_once_core(
    *,
    dry: bool,
    requested_mode: str,
    max_work_ms: Optional[int],
    max_queue_size: Optional[int],
    cooldown_sec: Optional[int],
    fallback_reason: str = "",
) -> Dict[str, Any]:
    gate = get_default_gate()
    slot = _slot()
    mode_in = _normalize_mode(requested_mode)

    effective_mode = mode_in
    mode_reasons: List[str] = []
    if slot != "B":
        effective_mode = "plan_only"
        mode_reasons.append("slot_a_forces_plan_only")
    if _SLOTB_DISABLED:
        effective_mode = "plan_only"
        mode_reasons.append("slot_b_disabled_in_process")
    if not _enqueue_enabled():
        effective_mode = "plan_only"
        mode_reasons.append("enqueue_disabled_by_env")
    if fallback_reason:
        mode_reasons.append(str(fallback_reason))

    budgets = _default_budgets(max_work_ms)
    queue_limit = _as_int(
        (max_queue_size if max_queue_size is not None else os.getenv("ESTER_PROACTIVITY_MAX_QUEUE_SIZE", "20")),
        20,
        min_value=1,
    )
    cooldown = _as_int(
        (cooldown_sec if cooldown_sec is not None else os.getenv("ESTER_PROACTIVITY_COOLDOWN_SEC", "120")),
        120,
        min_value=0,
    )

    target = _select_initiative(dry)
    if target is None:
        rep = {
            "ok": True,
            "no_work": True,
            "reason": "queue_empty",
            "slot": slot,
            "mode": effective_mode,
            "mode_reasons": mode_reasons,
            "queue_size": _queue_size(),
            "decisions_count": 0,
            "plan_id": "",
            "agent_id": "",
            "enqueue_id": "",
        }
        _update_runtime(
            dry=dry,
            mode=effective_mode,
            ok=True,
            error="",
            denied_at="",
            action_kind="",
            initiative_id="",
            plan_id="",
            template_id="",
            agent_id="",
        )
        return rep

    initiative_id = str(target.get("id") or ("initiative_" + uuid.uuid4().hex[:8]))
    title = str(target.get("title") or "initiative")
    chain_id = "chain_proactivity_" + uuid.uuid4().hex[:10]
    reason_h = f"initiative={initiative_id}; mode={effective_mode}; title={title[:80]}"

    out: Dict[str, Any] = {
        "ok": False,
        "slot": slot,
        "mode": effective_mode,
        "mode_requested": mode_in,
        "mode_reasons": mode_reasons,
        "initiative_id": initiative_id,
        "chain_id": chain_id,
        "plan_id": "",
        "plan_hash": "",
        "template_id": "",
        "agent_id": "",
        "enqueue_id": "",
        "queue_size": _queue_size(),
        "queue_size_before": _queue_size(),
        "decisions_count": 0,
        "denied_at": "",
        "error": "",
        "reason": "",
        "dry_run": bool(dry),
        "agent_run": {"ok": True, "skipped": True, "reason": "enqueue_only"},
        "decisions": {},
        "budgets": dict(budgets),
    }

    t0 = time.monotonic()
    plan_dec = _gate_decide(
        gate=gate,
        chain_id=chain_id,
        step="proactivity.plan",
        needs=["proactivity.plan"],
        actor="ester",
        intent="proactivity_plan",
        budgets=budgets,
        metadata={"initiative_id": initiative_id, "reason": reason_h},
    )
    out["decisions"]["proactivity.plan"] = plan_dec
    out["decisions_count"] += 1
    if not bool(plan_dec.get("allowed")):
        out["denied_at"] = "proactivity.plan"
        out["error"] = str(plan_dec.get("reason_code") or "volition_denied")
        _append_enqueue_log(
            dry=dry,
            chain_id=chain_id,
            initiative_id=initiative_id,
            plan_id="",
            plan_hash="",
            agent_id="",
            enqueue_id="",
            ok=False,
            error=out["error"],
        )
        _update_runtime(
            dry=dry,
            mode=effective_mode,
            ok=False,
            error=out["error"],
            denied_at=out["denied_at"],
            action_kind="proactivity.plan",
            initiative_id=initiative_id,
            plan_id="",
            template_id="",
            agent_id="",
        )
        return out

    plan_raw = planner_v1.build_plan(dict(target), dict(budgets))
    template = template_bridge.select_template(dict(target))
    template_id = str(template.get("template_id") or "planner.v1")
    queue_plan = _normalize_plan_for_queue(plan_raw, initiative_id=initiative_id, template_id=template_id)
    plan_id = str(queue_plan.get("plan_id") or "")
    plan_hash = _plan_hash(queue_plan)

    out["plan_id"] = plan_id
    out["plan_hash"] = plan_hash
    out["template_id"] = template_id
    out["plan"] = queue_plan
    out["template"] = template

    elapsed_ms = int((time.monotonic() - t0) * 1000.0)
    if elapsed_ms > int(budgets.get("max_work_ms") or 0):
        out["ok"] = True
        out["reason"] = "max_work_ms_exceeded"
        out["error"] = ""
        _append_enqueue_log(
            dry=dry,
            chain_id=chain_id,
            initiative_id=initiative_id,
            plan_id=plan_id,
            plan_hash=plan_hash,
            agent_id="",
            enqueue_id="",
            ok=True,
            error="max_work_ms_exceeded",
        )
        _update_runtime(
            dry=dry,
            mode=effective_mode,
            ok=True,
            error="",
            denied_at="",
            action_kind="proactivity.plan",
            initiative_id=initiative_id,
            plan_id=plan_id,
            template_id=template_id,
            agent_id="",
        )
        return out

    queue_before = _queue_size()
    out["queue_size_before"] = queue_before
    if queue_before >= queue_limit:
        out["ok"] = True
        out["reason"] = "queue_full"
        out["error"] = ""
        _append_enqueue_log(
            dry=dry,
            chain_id=chain_id,
            initiative_id=initiative_id,
            plan_id=plan_id,
            plan_hash=plan_hash,
            agent_id="",
            enqueue_id="",
            ok=True,
            error="queue_full",
        )
        _update_runtime(
            dry=dry,
            mode=effective_mode,
            ok=True,
            error="",
            denied_at="",
            action_kind="proactivity.plan",
            initiative_id=initiative_id,
            plan_id=plan_id,
            template_id=template_id,
            agent_id="",
        )
        return out

    dedupe = _dedupe_hit(initiative_id, plan_hash, cooldown)
    if bool(dedupe.get("hit")):
        out["ok"] = True
        out["reason"] = "cooldown_dedupe"
        out["enqueue_id"] = str(dedupe.get("enqueue_id") or "")
        _append_enqueue_log(
            dry=dry,
            chain_id=chain_id,
            initiative_id=initiative_id,
            plan_id=plan_id,
            plan_hash=plan_hash,
            agent_id="",
            enqueue_id=out["enqueue_id"],
            ok=True,
            error="cooldown_dedupe",
        )
        _update_runtime(
            dry=dry,
            mode=effective_mode,
            ok=True,
            error="",
            denied_at="",
            action_kind="proactivity.plan",
            initiative_id=initiative_id,
            plan_id=plan_id,
            template_id=template_id,
            agent_id="",
        )
        return out

    if effective_mode == "plan_only":
        _mark_processed(
            dry=dry,
            initiative_id=initiative_id,
            status="planned",
            note="iter42_plan_only",
            agent_id="",
            chain_id=chain_id,
        )
        out["ok"] = True
        out["reason"] = "plan_only"
        out["queue_size"] = _queue_size()
        _append_enqueue_log(
            dry=dry,
            chain_id=chain_id,
            initiative_id=initiative_id,
            plan_id=plan_id,
            plan_hash=plan_hash,
            agent_id="",
            enqueue_id="",
            ok=True,
            error="plan_only",
        )
        _update_runtime(
            dry=dry,
            mode=effective_mode,
            ok=True,
            error="",
            denied_at="",
            action_kind="proactivity.plan",
            initiative_id=initiative_id,
            plan_id=plan_id,
            template_id=template_id,
            agent_id="",
        )
        return out

    if (not dry) and _agent_create_requires_approval():
        default_agent_id = _find_agent_id_by_name("proactivity.enqueue.default")
        if not default_agent_id:
            if agent_create_approval is None:
                out["ok"] = False
                out["error"] = "agent_create_approval_store_unavailable"
                _append_enqueue_log(
                    dry=dry,
                    chain_id=chain_id,
                    initiative_id=initiative_id,
                    plan_id=plan_id,
                    plan_hash=plan_hash,
                    agent_id="",
                    enqueue_id="",
                    ok=False,
                    error=out["error"],
                )
                _update_runtime(
                    dry=dry,
                    mode=effective_mode,
                    ok=False,
                    error=out["error"],
                    denied_at="",
                    action_kind="agent.create.await_approval",
                    initiative_id=initiative_id,
                    plan_id=plan_id,
                    template_id=template_id,
                    agent_id="",
                )
                return out

            req_rep = agent_create_approval.request(
                source="modules.proactivity.executor",
                template_id=str(template_id or "initiator.v1"),
                name="proactivity.enqueue.default",
                goal=str(title or "proactivity enqueue"),
                overrides={
                    "name": "proactivity.enqueue.default",
                    "goal": str(title or "proactivity enqueue"),
                    "owner": "modules.proactivity.executor",
                },
                meta={
                    "initiative_id": initiative_id,
                    "plan_id": plan_id,
                    "chain_id": chain_id,
                },
                dedupe_key=f"proactivity.enqueue.default:{template_id}",
            )
            if not bool(req_rep.get("ok")):
                out["ok"] = False
                out["error"] = str(req_rep.get("error") or "agent_create_approval_request_failed")
                _append_enqueue_log(
                    dry=dry,
                    chain_id=chain_id,
                    initiative_id=initiative_id,
                    plan_id=plan_id,
                    plan_hash=plan_hash,
                    agent_id="",
                    enqueue_id="",
                    ok=False,
                    error=out["error"],
                )
                _update_runtime(
                    dry=dry,
                    mode=effective_mode,
                    ok=False,
                    error=out["error"],
                    denied_at="",
                    action_kind="agent.create.await_approval",
                    initiative_id=initiative_id,
                    plan_id=plan_id,
                    template_id=template_id,
                    agent_id="",
                )
                return out

            out["ok"] = True
            out["reason"] = "awaiting_agent_create_approval"
            out["approval_request"] = dict(req_rep.get("request") or {})
            out["queue_size"] = _queue_size()
            _append_enqueue_log(
                dry=dry,
                chain_id=chain_id,
                initiative_id=initiative_id,
                plan_id=plan_id,
                plan_hash=plan_hash,
                agent_id="",
                enqueue_id="",
                ok=True,
                error="awaiting_agent_create_approval",
            )
            _update_runtime(
                dry=dry,
                mode=effective_mode,
                ok=True,
                error="",
                denied_at="",
                action_kind="agent.create.await_approval",
                initiative_id=initiative_id,
                plan_id=plan_id,
                template_id=template_id,
                agent_id="",
            )
            return out

    create_dec = _gate_decide(
        gate=gate,
        chain_id=chain_id,
        step="agent.create",
        needs=["agent.create"],
        actor="ester",
        intent="proactivity_agent_create",
        budgets=budgets,
        metadata={
            "initiative_id": initiative_id,
            "plan_id": plan_id,
            "template_id": template_id,
            "reason": reason_h,
        },
    )
    out["decisions"]["agent.create"] = create_dec
    out["decisions_count"] += 1
    if not bool(create_dec.get("allowed")):
        out["denied_at"] = "agent.create"
        out["error"] = str(create_dec.get("reason_code") or "volition_denied")
        _append_enqueue_log(
            dry=dry,
            chain_id=chain_id,
            initiative_id=initiative_id,
            plan_id=plan_id,
            plan_hash=plan_hash,
            agent_id="",
            enqueue_id="",
            ok=False,
            error=out["error"],
        )
        _update_runtime(
            dry=dry,
            mode=effective_mode,
            ok=False,
            error=out["error"],
            denied_at=out["denied_at"],
            action_kind="agent.create",
            initiative_id=initiative_id,
            plan_id=plan_id,
            template_id=template_id,
            agent_id="",
        )
        return out

    agent_rep = _ensure_default_agent(
        dry=dry,
        title=title,
        template=template,
        queue_plan=queue_plan,
        budgets=budgets,
    )
    out["agent_create"] = agent_rep
    if not bool(agent_rep.get("ok")):
        out["error"] = str(agent_rep.get("error") or "agent_create_failed")
        _append_enqueue_log(
            dry=dry,
            chain_id=chain_id,
            initiative_id=initiative_id,
            plan_id=plan_id,
            plan_hash=plan_hash,
            agent_id="",
            enqueue_id="",
            ok=False,
            error=out["error"],
        )
        _update_runtime(
            dry=dry,
            mode=effective_mode,
            ok=False,
            error=out["error"],
            denied_at="",
            action_kind="agent.create",
            initiative_id=initiative_id,
            plan_id=plan_id,
            template_id=template_id,
            agent_id="",
        )
        return out

    agent_id = str(agent_rep.get("agent_id") or "")
    out["agent_id"] = agent_id

    enqueue_payload = {
        "plan": queue_plan,
        "agent_id": agent_id,
        "priority": 50,
        "challenge_sec": _as_int(os.getenv("ESTER_PROACTIVITY_CHALLENGE_SEC", "60"), 60, min_value=0),
        "actor": "ester",
        "reason": f"proactivity_enqueue:{initiative_id}",
        "plan_id": plan_id,
        "initiative_id": initiative_id,
        "plan_hash": plan_hash,
    }

    if dry:
        enqueue_dec = _gate_decide(
            gate=gate,
            chain_id=chain_id,
            step="agent.queue.enqueue",
            needs=["agent.queue.enqueue"],
            actor="ester",
            intent="proactivity_enqueue",
            budgets=budgets,
            metadata={
                "initiative_id": initiative_id,
                "plan_id": plan_id,
                "template_id": template_id,
                "agent_id": agent_id,
                "reason": reason_h,
                "dry_run": True,
            },
        )
        out["decisions"]["agent.queue.enqueue"] = enqueue_dec
        out["decisions_count"] += 1
        if not bool(enqueue_dec.get("allowed")):
            out["denied_at"] = "agent.queue.enqueue"
            out["error"] = str(enqueue_dec.get("reason_code") or "volition_denied")
            _update_runtime(
                dry=dry,
                mode=effective_mode,
                ok=False,
                error=out["error"],
                denied_at=out["denied_at"],
                action_kind="agent.queue.enqueue",
                initiative_id=initiative_id,
                plan_id=plan_id,
                template_id=template_id,
                agent_id=agent_id,
            )
            return out
        enqueue_rep: Dict[str, Any] = {"ok": True, "dry_run": True, "queue_id": ""}
    else:
        enqueue_rep = _enqueue_via_action(
            gate=gate,
            chain_id=chain_id,
            budgets=budgets,
            actor="ester",
            payload=enqueue_payload,
        )
        out["decisions_count"] += 1

    out["enqueue"] = enqueue_rep
    if not bool(enqueue_rep.get("ok")):
        out["denied_at"] = "agent.queue.enqueue" if str(enqueue_rep.get("error") or "") == "volition_denied" else ""
        out["error"] = str(enqueue_rep.get("error") or "enqueue_failed")
        _append_enqueue_log(
            dry=dry,
            chain_id=chain_id,
            initiative_id=initiative_id,
            plan_id=plan_id,
            plan_hash=plan_hash,
            agent_id=agent_id,
            enqueue_id="",
            ok=False,
            error=out["error"],
        )
        _update_runtime(
            dry=dry,
            mode=effective_mode,
            ok=False,
            error=out["error"],
            denied_at=out["denied_at"],
            action_kind="agent.queue.enqueue",
            initiative_id=initiative_id,
            plan_id=plan_id,
            template_id=template_id,
            agent_id=agent_id,
        )
        return out

    enqueue_id = str(enqueue_rep.get("queue_id") or "")
    out["enqueue_id"] = enqueue_id
    out["queue_size"] = _queue_size()

    _mark_processed(
        dry=dry,
        initiative_id=initiative_id,
        status="planned",
        note=("iter42_enqueued:" + enqueue_id),
        agent_id=agent_id,
        chain_id=chain_id,
    )

    out["ok"] = True
    out["reason"] = "enqueued"

    _append_enqueue_log(
        dry=dry,
        chain_id=chain_id,
        initiative_id=initiative_id,
        plan_id=plan_id,
        plan_hash=plan_hash,
        agent_id=agent_id,
        enqueue_id=enqueue_id,
        ok=True,
        error="",
    )
    _update_runtime(
        dry=dry,
        mode=effective_mode,
        ok=True,
        error="",
        denied_at="",
        action_kind="agent.queue.enqueue",
        initiative_id=initiative_id,
        plan_id=plan_id,
        template_id=template_id,
        agent_id=agent_id,
    )
    return out


def run_once(
    dry: bool = False,
    *,
    mode: str = "enqueue",
    max_work_ms: Optional[int] = None,
    max_queue_size: Optional[int] = None,
    cooldown_sec: Optional[int] = None,
) -> Dict[str, Any]:
    global _SLOTB_ERR_STREAK, _SLOTB_DISABLED

    requested_mode = _normalize_mode(mode)
    slot = _slot()

    try:
        rep = _run_once_core(
            dry=bool(dry),
            requested_mode=requested_mode,
            max_work_ms=max_work_ms,
            max_queue_size=max_queue_size,
            cooldown_sec=cooldown_sec,
        )
        if bool(rep.get("ok")):
            _SLOTB_ERR_STREAK = 0
        return rep
    except Exception as exc:
        _SLOTB_ERR_STREAK += 1
        err = f"{exc.__class__.__name__}: {exc}"

        if slot == "B" and requested_mode == "enqueue" and _SLOTB_ERR_STREAK >= _slot_b_fail_max():
            _SLOTB_DISABLED = True
            try:
                fallback = _run_once_core(
                    dry=bool(dry),
                    requested_mode="plan_only",
                    max_work_ms=max_work_ms,
                    max_queue_size=max_queue_size,
                    cooldown_sec=cooldown_sec,
                    fallback_reason="slot_b_auto_rollback",
                )
                fallback.setdefault("fallback", {})
                fallback["fallback"] = {
                    "trigger": "slot_b_auto_rollback",
                    "error": err,
                    "streak": _SLOTB_ERR_STREAK,
                }
                return fallback
            except Exception as fallback_exc:
                return {
                    "ok": False,
                    "slot": slot,
                    "mode": "plan_only",
                    "error": "slot_b_runtime_error",
                    "detail": err,
                    "fallback_error": f"{fallback_exc.__class__.__name__}: {fallback_exc}",
                }

        return {
            "ok": False,
            "slot": slot,
            "mode": requested_mode,
            "error": "slot_runtime_error",
            "detail": err,
            "streak": _SLOTB_ERR_STREAK,
        }


__all__ = ["run_once"]

