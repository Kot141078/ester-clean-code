# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.agents import plan_schema
from modules.thinking import action_registry

_LOCK = threading.RLock()
_LIVE_STATUSES = {"enqueued", "claimed", "running"}
_STRICT_FORBIDDEN_WARNING_CODES = {
    "unknown_step_keys",
    "unknown_plan_keys",
    "unknown_budget_keys",
}


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _agents_dir() -> Path:
    p = (_persist_dir() / "agents").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _queue_path() -> Path:
    p = (_agents_dir() / "queue.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def queue_path() -> Path:
    return _queue_path()


def _now_ts() -> int:
    return int(time.time())


def _detail(level: str, code: str, message: str, **extra: Any) -> Dict[str, Any]:
    row = {
        "level": str(level or "error"),
        "code": str(code or "invalid"),
        "message": str(message or ""),
    }
    if extra:
        row.update(dict(extra))
    return row


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    return bool(default)


def _template_requires_approval(template_id: str) -> Optional[bool]:
    tid = str(template_id or "").strip()
    if not tid:
        return None
    try:
        from modules.garage.templates.pack_v1 import by_id as _templates_by_id

        tpl = dict((_templates_by_id() or {}).get(tid) or {})
    except Exception:
        return None
    if not tpl:
        return None
    queue_policy = dict(tpl.get("queue_policy") or {})
    if "requires_approval" not in queue_policy:
        return None
    return bool(_as_bool(queue_policy.get("requires_approval"), False))


def _agent_enabled_state(agent_id: str) -> Optional[bool]:
    """
    Returns:
      True  -> agent exists and enabled
      False -> agent exists and disabled
      None  -> unknown/unavailable (legacy compatibility path)
    """
    aid = str(agent_id or "").strip()
    if not aid:
        return None
    try:
        from modules.garage import agent_factory

        rep = agent_factory.get_agent(aid)
    except Exception:
        return None
    if not bool(rep.get("ok")):
        return None
    row = dict(rep.get("agent") or {})
    spec = dict(row.get("spec") or {})
    enabled = bool(spec.get("enabled", row.get("enabled", True)))
    return bool(enabled)


def _agent_requires_approval(agent_id: str) -> Optional[bool]:
    aid = str(agent_id or "").strip()
    if not aid:
        return None
    try:
        from modules.garage import agent_factory

        rep = agent_factory.get_agent(aid)
    except Exception:
        return None
    if not bool(rep.get("ok")):
        return None
    row = dict(rep.get("agent") or {})
    spec = dict(row.get("spec") or {})
    queue_policy = dict(spec.get("queue_policy") or row.get("queue_policy") or {})
    if "requires_approval" in queue_policy:
        return bool(_as_bool(queue_policy.get("requires_approval"), False))
    template_id = str(spec.get("template_id") or row.get("template_id") or "").strip()
    if not template_id:
        return None
    tpl_requires = _template_requires_approval(template_id)
    if tpl_requires is None:
        return None
    return bool(tpl_requires)


def _warnings_from_details(details: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for row in list(details or []):
        if str((row or {}).get("level") or "") != "warn":
            continue
        code = str((row or {}).get("code") or "").strip()
        if code and code not in out:
            out.append(code)
    return out


def _error_codes(details: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for row in list(details or []):
        if str((row or {}).get("level") or "") != "error":
            continue
        code = str((row or {}).get("code") or "").strip()
        if code and code not in out:
            out.append(code)
    return out


def _load_from_path(plan_path: str) -> Dict[str, Any]:
    if not str(plan_path or "").strip():
        return {"ok": False, "error": "plan_path_required", "details": []}
    return plan_schema.load_plan_from_path(str(plan_path))


def _normalize_validate_plan(plan: Any, *, plan_path: str = "") -> Dict[str, Any]:
    strict = bool(plan_schema.strict_enabled())
    details: List[Dict[str, Any]] = []
    warnings: List[str] = []
    source_plan = plan

    try:
        if str(plan_path or "").strip():
            load_rep = _load_from_path(plan_path)
            details.extend(list(load_rep.get("details") or []))
            warnings.extend(_warnings_from_details(list(load_rep.get("details") or [])))
            if bool(load_rep.get("ok")):
                source_plan = load_rep.get("plan")
            elif strict:
                return {
                    "ok": False,
                    "error": "plan_invalid",
                    "details": details,
                    "warnings": warnings,
                    "plan": None,
                    "plan_hash": "",
                    "strict": strict,
                    "strict_status": plan_schema.strict_status(),
                }
            else:
                if "plan_path_lenient_mode" not in warnings:
                    warnings.append("plan_path_lenient_mode")

        src_obj = source_plan
        if isinstance(src_obj, list):
            src_obj = {"steps": list(src_obj)}

        norm = plan_schema.normalize_plan(src_obj)
        norm_details = list(norm.get("details") or [])
        details.extend(norm_details)
        warnings.extend(_warnings_from_details(norm_details))
        normalized = norm.get("plan")

        if not bool(norm.get("ok")):
            if strict:
                return {
                    "ok": False,
                    "error": "plan_invalid",
                    "details": details,
                    "warnings": warnings,
                    "plan": normalized,
                    "plan_hash": "",
                    "strict": strict,
                    "strict_status": plan_schema.strict_status(),
                }
            if "plan_lenient_mode" not in warnings:
                warnings.append("plan_lenient_mode")
            if normalized is None:
                normalized = src_obj if isinstance(src_obj, dict) else {"steps": []}

        if strict:
            forbidden = [x for x in _warnings_from_details(norm_details) if x in _STRICT_FORBIDDEN_WARNING_CODES]
            if forbidden:
                for code in forbidden:
                    details.append(
                        _detail(
                            "error",
                            code,
                            "strict schema forbids unknown keys",
                            strict=True,
                        )
                    )
                return {
                    "ok": False,
                    "error": "plan_invalid",
                    "details": details,
                    "warnings": warnings,
                    "plan": normalized,
                    "plan_hash": "",
                    "strict": strict,
                    "strict_status": plan_schema.strict_status(),
                }

        val = plan_schema.validate_plan(dict(normalized or {}), registry=action_registry)
        details.extend(list(val.get("details") or []))
        ph = str(val.get("plan_hash") or "")

        if not bool(val.get("ok")):
            if strict:
                return {
                    "ok": False,
                    "error": "plan_invalid",
                    "details": details,
                    "warnings": warnings,
                    "plan": normalized,
                    "plan_hash": ph,
                    "strict": strict,
                    "strict_status": plan_schema.strict_status(),
                }
            if "plan_lenient_mode" not in warnings:
                warnings.append("plan_lenient_mode")
            for code in _error_codes(list(val.get("details") or [])):
                marker = "lenient_" + code
                if marker not in warnings:
                    warnings.append(marker)
        elif strict:
            plan_schema.note_strict_success()

        return {
            "ok": True,
            "error": "",
            "details": details,
            "warnings": warnings,
            "plan": dict(normalized or {}),
            "plan_hash": ph,
            "strict": strict,
            "strict_status": plan_schema.strict_status(),
        }
    except Exception as exc:
        if strict:
            status = plan_schema.note_strict_exception("agent_queue.enqueue", exc)
            details.append(
                _detail(
                    "error",
                    "plan_schema_exception",
                    "strict plan schema crashed",
                    where="agent_queue.enqueue",
                    detail=f"{exc.__class__.__name__}: {exc}",
                )
            )
            if bool(status.get("strict_enabled")):
                return {
                    "ok": False,
                    "error": "plan_invalid",
                    "details": details,
                    "warnings": warnings,
                    "plan": None,
                    "plan_hash": "",
                    "strict": True,
                    "strict_status": status,
                }
            if "plan_schema_auto_rollback" not in warnings:
                warnings.append("plan_schema_auto_rollback")
        if "plan_lenient_mode" not in warnings:
            warnings.append("plan_lenient_mode")
        if "plan_schema_exception" not in warnings:
            warnings.append("plan_schema_exception")
        fallback_plan: Any = source_plan
        if isinstance(fallback_plan, list):
            fallback_plan = {"steps": list(fallback_plan)}
        if not isinstance(fallback_plan, dict):
            fallback_plan = {"steps": []}
        return {
            "ok": True,
            "error": "",
            "details": details,
            "warnings": warnings,
            "plan": dict(fallback_plan),
            "plan_hash": "",
            "strict": False,
            "strict_status": plan_schema.strict_status(),
        }


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(dict(row or {}), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


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


def events() -> List[Dict[str, Any]]:
    with _LOCK:
        return _read_jsonl(_queue_path())


def append_event(
    event_type: str,
    *,
    queue_id: str,
    actor: str = "",
    reason: str = "",
    priority: Optional[int] = None,
    not_before_ts: Optional[int] = None,
    plan: Any = None,
    plan_path: str = "",
    agent_id: str = "",
    requires_approval: Optional[bool] = None,
    approved: Optional[bool] = None,
    approved_ts: Optional[int] = None,
    approved_by: str = "",
    approved_reason: str = "",
    run_id: str = "",
    error: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    qid = str(queue_id or "").strip()
    et = str(event_type or "").strip().lower()
    if not qid:
        return {"ok": False, "error": "queue_id_required"}
    if et not in {"enqueue", "claim", "start", "done", "fail", "cancel", "expire", "approve"}:
        return {"ok": False, "error": "event_type_invalid", "event_type": et}

    now = _now_ts()
    row: Dict[str, Any] = {
        "ts": now,
        "type": et,
        "event": et,
        "queue_id": qid,
        "actor": str(actor or "").strip(),
        "reason": str(reason or "").strip(),
    }
    if priority is not None:
        row["priority"] = int(priority)
    if not_before_ts is not None:
        row["not_before_ts"] = int(not_before_ts)
    if plan is not None:
        row["plan"] = plan
    if plan_path:
        row["plan_path"] = str(plan_path)
    if agent_id:
        row["agent_id"] = str(agent_id)
    if requires_approval is not None:
        row["requires_approval"] = bool(_as_bool(requires_approval, False))
    if approved is not None:
        row["approved"] = bool(_as_bool(approved, False))
    if approved_ts is not None:
        row["approved_ts"] = int(approved_ts)
    if approved_by:
        row["approved_by"] = str(approved_by)
    if approved_reason:
        row["approved_reason"] = str(approved_reason)
    if run_id:
        row["run_id"] = str(run_id)
    if error:
        row["error"] = str(error)
    if extra:
        row["extra"] = dict(extra)

    with _LOCK:
        _append_jsonl(_queue_path(), row)
    return {"ok": True, "event": row}


def enqueue(
    plan: Any,
    *,
    priority: int = 50,
    challenge_sec: int = 60,
    not_before_ts: Optional[int] = None,
    actor: str = "ester",
    reason: str = "",
    plan_path: str = "",
    agent_id: str = "",
    requires_approval: Optional[bool] = None,
    approved: Optional[bool] = None,
    queue_id: str = "",
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if aid:
        enabled = _agent_enabled_state(aid)
        if enabled is False:
            return {"ok": False, "error": "agent_disabled", "agent_id": aid}

    requires_approval_eff = bool(_as_bool(requires_approval, False))
    if requires_approval is None and aid:
        requires_by_policy = _agent_requires_approval(aid)
        if requires_by_policy is True:
            requires_approval_eff = True
    approved_eff = bool(_as_bool(approved, False))

    prep = _normalize_validate_plan(plan, plan_path=str(plan_path or ""))
    if not bool(prep.get("ok")):
        return {
            "ok": False,
            "error": "plan_invalid",
            "details": list(prep.get("details") or []),
            "warnings": list(prep.get("warnings") or []),
            "slot": _slot(),
            "strict_status": dict(prep.get("strict_status") or {}),
        }

    normalized_plan = prep.get("plan")
    if not isinstance(normalized_plan, dict):
        normalized_plan = {"steps": []}

    qid = str(queue_id or ("q_" + uuid.uuid4().hex[:12])).strip()
    now = _now_ts()
    nb = int(not_before_ts) if not_before_ts is not None else now + max(0, int(challenge_sec or 0))
    rep = append_event(
        "enqueue",
        queue_id=qid,
        actor=actor,
        reason=reason,
        priority=max(0, int(priority or 0)),
        not_before_ts=nb,
        plan=normalized_plan,
        plan_path=plan_path,
        agent_id=aid,
        requires_approval=requires_approval_eff,
        approved=approved_eff,
    )
    if not bool(rep.get("ok")):
        return rep
    out = {
        "ok": True,
        "queue_id": qid,
        "priority": max(0, int(priority or 0)),
        "not_before_ts": nb,
        "challenge_sec": max(0, int(nb - now)),
        "slot": _slot(),
        "requires_approval": bool(requires_approval_eff),
        "approved": bool(approved_eff),
    }
    warnings = [str(x) for x in list(prep.get("warnings") or []) if str(x).strip()]
    if warnings:
        out["warnings"] = warnings
    plan_hash = str(prep.get("plan_hash") or "")
    if plan_hash:
        out["plan_hash"] = plan_hash
    return out


def _load_item_for_transition(queue_id: str) -> Dict[str, Any]:
    st = fold_state()
    item = dict((st.get("items_by_id") or {}).get(str(queue_id or "").strip()) or {})
    return item


def claim(queue_id: str, *, actor: str = "ester", reason: str = "") -> Dict[str, Any]:
    item = _load_item_for_transition(queue_id)
    if not item:
        return {"ok": False, "error": "queue_not_found", "queue_id": str(queue_id or "")}
    if str(item.get("status") or "") != "enqueued":
        return {"ok": False, "error": "queue_not_enqueued", "queue_id": str(queue_id or ""), "status": item.get("status")}
    return append_event("claim", queue_id=str(queue_id), actor=actor, reason=reason)


def start(
    queue_id: str,
    *,
    actor: str = "ester",
    reason: str = "",
    run_id: str = "",
    agent_id: str = "",
) -> Dict[str, Any]:
    item = _load_item_for_transition(queue_id)
    if not item:
        return {"ok": False, "error": "queue_not_found", "queue_id": str(queue_id or "")}
    if str(item.get("status") or "") not in {"claimed", "enqueued"}:
        return {"ok": False, "error": "queue_not_claimed", "queue_id": str(queue_id or ""), "status": item.get("status")}
    return append_event("start", queue_id=str(queue_id), actor=actor, reason=reason, run_id=run_id, agent_id=agent_id)


def done(
    queue_id: str,
    *,
    actor: str = "ester",
    reason: str = "",
    run_id: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    item = _load_item_for_transition(queue_id)
    if not item:
        return {"ok": False, "error": "queue_not_found", "queue_id": str(queue_id or "")}
    if str(item.get("status") or "") not in {"running", "claimed"}:
        return {"ok": False, "error": "queue_not_running", "queue_id": str(queue_id or ""), "status": item.get("status")}
    return append_event("done", queue_id=str(queue_id), actor=actor, reason=reason, run_id=run_id, extra=extra)


def fail(
    queue_id: str,
    *,
    actor: str = "ester",
    reason: str = "",
    run_id: str = "",
    error: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    item = _load_item_for_transition(queue_id)
    if not item:
        return {"ok": False, "error": "queue_not_found", "queue_id": str(queue_id or "")}
    if str(item.get("status") or "") not in {"running", "claimed", "enqueued"}:
        return {"ok": False, "error": "queue_not_active", "queue_id": str(queue_id or ""), "status": item.get("status")}
    return append_event(
        "fail",
        queue_id=str(queue_id),
        actor=actor,
        reason=reason,
        run_id=run_id,
        error=error,
        extra=extra,
    )


def cancel(queue_id: str, *, actor: str = "ester", reason: str = "") -> Dict[str, Any]:
    item = _load_item_for_transition(queue_id)
    if not item:
        return {"ok": False, "error": "queue_not_found", "queue_id": str(queue_id or "")}
    if str(item.get("status") or "") not in {"enqueued", "claimed"}:
        return {"ok": False, "error": "queue_not_cancelable", "queue_id": str(queue_id or ""), "status": item.get("status")}
    return append_event("cancel", queue_id=str(queue_id), actor=actor, reason=reason)


def expire(queue_id: str, *, actor: str = "system", reason: str = "expired") -> Dict[str, Any]:
    item = _load_item_for_transition(queue_id)
    if not item:
        return {"ok": False, "error": "queue_not_found", "queue_id": str(queue_id or "")}
    if str(item.get("status") or "") not in {"enqueued", "claimed"}:
        return {"ok": False, "error": "queue_not_expirable", "queue_id": str(queue_id or ""), "status": item.get("status")}
    return append_event("expire", queue_id=str(queue_id), actor=actor, reason=reason)


def approve(queue_id: str, *, actor: str = "ester", reason: str = "") -> Dict[str, Any]:
    qid = str(queue_id or "").strip()
    if not qid:
        return {"ok": False, "error": "queue_id_required"}
    item = _load_item_for_transition(qid)
    if not item:
        return {"ok": False, "error": "queue_not_found", "queue_id": qid}
    status = str(item.get("status") or "")
    if status in {"done", "failed", "canceled", "expired"}:
        return {"ok": False, "error": "not_approvable", "queue_id": qid, "status": status}
    if bool(item.get("approved")):
        return {
            "ok": True,
            "queue_id": qid,
            "approved": True,
            "approved_ts": int(item.get("approved_ts") or 0),
            "approved_by": str(item.get("approved_by") or ""),
            "approved_reason": str(item.get("approved_reason") or ""),
            "idempotent": True,
        }
    rep = append_event("approve", queue_id=qid, actor=actor, reason=reason)
    if not bool(rep.get("ok")):
        return rep
    ev = dict(rep.get("event") or {})
    return {
        "ok": True,
        "queue_id": qid,
        "approved": True,
        "approved_ts": int(ev.get("ts") or _now_ts()),
        "approved_by": str(ev.get("actor") or ""),
        "approved_reason": str(ev.get("reason") or ""),
    }


def cancel_for_agent(agent_id: str, *, actor: str = "system", reason: str = "agent_disabled") -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return {"ok": False, "error": "agent_id_required"}
    st = fold_state()
    targets = [
        dict(row)
        for row in list(st.get("items") or [])
        if str((row or {}).get("agent_id") or "").strip() == aid
        and str((row or {}).get("status") or "") in {"enqueued", "claimed"}
    ]
    canceled_ids: List[str] = []
    for row in targets:
        qid = str(row.get("queue_id") or "").strip()
        if not qid:
            continue
        rep = cancel(qid, actor=actor, reason=reason)
        if bool(rep.get("ok")):
            canceled_ids.append(qid)
    return {
        "ok": True,
        "agent_id": aid,
        "canceled": len(canceled_ids),
        "queue_ids": canceled_ids,
    }


def fold_state() -> Dict[str, Any]:
    with _LOCK:
        evs = _read_jsonl(_queue_path())

    items: Dict[str, Dict[str, Any]] = {}
    for raw in evs:
        et = str(raw.get("type") or raw.get("event") or "").strip().lower()
        qid = str(raw.get("queue_id") or "").strip()
        ts = int(raw.get("ts") or 0)
        if not qid:
            continue
        if et == "enqueue":
            item = {
                "queue_id": qid,
                "status": "enqueued",
                "enqueue_ts": ts,
                "updated_ts": ts,
                "priority": int(raw.get("priority") or 50),
                "not_before_ts": int(raw.get("not_before_ts") or ts),
                "plan": raw.get("plan"),
                "plan_path": str(raw.get("plan_path") or ""),
                "agent_id": str(raw.get("agent_id") or ""),
                "actor": str(raw.get("actor") or ""),
                "reason": str(raw.get("reason") or ""),
                "requires_approval": bool(_as_bool(raw.get("requires_approval"), False)),
                "approved": bool(_as_bool(raw.get("approved"), False)),
                "approved_ts": int(raw.get("approved_ts") or 0),
                "approved_by": str(raw.get("approved_by") or ""),
                "approved_reason": str(raw.get("approved_reason") or ""),
                "run_id": "",
                "error": "",
            }
            items[qid] = item
            continue

        item = items.get(qid)
        if not item:
            continue
        item["updated_ts"] = ts
        if "agent_id" in raw and str(raw.get("agent_id") or "").strip():
            item["agent_id"] = str(raw.get("agent_id") or "")
        if "run_id" in raw and str(raw.get("run_id") or "").strip():
            item["run_id"] = str(raw.get("run_id") or "")
        if "requires_approval" in raw:
            item["requires_approval"] = bool(_as_bool(raw.get("requires_approval"), bool(item.get("requires_approval"))))
        if "approved" in raw:
            item["approved"] = bool(_as_bool(raw.get("approved"), bool(item.get("approved"))))
        if "approved_ts" in raw:
            item["approved_ts"] = int(raw.get("approved_ts") or 0)
        if "approved_by" in raw and str(raw.get("approved_by") or "").strip():
            item["approved_by"] = str(raw.get("approved_by") or "")
        if "approved_reason" in raw and str(raw.get("approved_reason") or "").strip():
            item["approved_reason"] = str(raw.get("approved_reason") or "")
        if et == "claim":
            item["status"] = "claimed"
            item["claim_ts"] = ts
            item["claim_actor"] = str(raw.get("actor") or "")
        elif et == "start":
            item["status"] = "running"
            item["start_ts"] = ts
        elif et == "done":
            item["status"] = "done"
            item["finish_ts"] = ts
            item["done_reason"] = str(raw.get("reason") or "")
            item["result"] = dict(raw.get("extra") or {})
        elif et == "fail":
            item["status"] = "failed"
            item["finish_ts"] = ts
            item["error"] = str(raw.get("error") or raw.get("reason") or "failed")
            item["result"] = dict(raw.get("extra") or {})
        elif et == "cancel":
            item["status"] = "canceled"
            item["cancel_ts"] = ts
        elif et == "expire":
            item["status"] = "expired"
            item["expire_ts"] = ts
        elif et == "approve":
            item["approved"] = True
            item["approved_ts"] = ts
            item["approved_by"] = str(raw.get("actor") or "")
            item["approved_reason"] = str(raw.get("reason") or "")

    rows = [dict(v) for _, v in sorted(items.items(), key=lambda kv: (int((kv[1] or {}).get("enqueue_ts") or 0), kv[0]))]
    live = [dict(r) for r in rows if str(r.get("status") or "") in _LIVE_STATUSES]
    stats: Dict[str, int] = {}
    for row in rows:
        s = str(row.get("status") or "")
        stats[s] = int(stats.get(s, 0)) + 1
    return {
        "ok": True,
        "events_total": len(evs),
        "items_total": len(rows),
        "stats": stats,
        "items": rows,
        "live": live,
        "live_total": len(live),
        "items_by_id": {str(r.get("queue_id") or ""): r for r in rows},
    }


def select_next(*, now_ts: Optional[int] = None, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    st = dict(state or fold_state())
    now = int(now_ts if now_ts is not None else _now_ts())
    enqueued = [dict(r) for r in list(st.get("items") or []) if str(r.get("status") or "") == "enqueued"]
    if not enqueued:
        return {"ok": True, "found": False, "reason": "queue_empty"}

    ready: List[Dict[str, Any]] = []
    pending: List[Dict[str, Any]] = []
    for row in enqueued:
        nb = int(row.get("not_before_ts") or 0)
        if now >= nb:
            ready.append(row)
        else:
            pending.append(row)

    if not ready:
        next_row = min(pending, key=lambda r: int(r.get("not_before_ts") or 0))
        wait_sec = max(0, int(next_row.get("not_before_ts") or 0) - now)
        return {
            "ok": True,
            "found": False,
            "reason": "challenge_window",
            "next_not_before_ts": int(next_row.get("not_before_ts") or 0),
            "wait_sec": wait_sec,
            "queue_id": str(next_row.get("queue_id") or ""),
        }

    ready.sort(
        key=lambda r: (
            -int(r.get("priority") or 0),
            int(r.get("enqueue_ts") or 0),
            str(r.get("queue_id") or ""),
        )
    )
    canceled = 0
    scanned = 0
    max_scan = max(1, min(50, len(ready)))
    for row in ready:
        if scanned >= max_scan:
            break
        scanned += 1
        candidate = dict(row)
        aid = str(candidate.get("agent_id") or "").strip()
        if aid:
            enabled = _agent_enabled_state(aid)
            if enabled is False:
                qid = str(candidate.get("queue_id") or "").strip()
                if qid:
                    rep = cancel(qid, actor="system", reason="agent_disabled")
                    if bool(rep.get("ok")):
                        canceled += 1
                continue
        return {"ok": True, "found": True, "candidate": candidate}
    if canceled > 0:
        return {"ok": True, "found": False, "reason": "agent_disabled_all", "canceled": int(canceled)}
    return {"ok": True, "found": False, "reason": "queue_empty"}


def list_queue(*, live_only: bool = False) -> Dict[str, Any]:
    st = fold_state()
    rows = list(st.get("live") or []) if bool(live_only) else list(st.get("items") or [])
    return {
        "ok": True,
        "count": len(rows),
        "items": rows,
        "live_only": bool(live_only),
        "stats": dict(st.get("stats") or {}),
    }


def load_plan(item: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(item or {})
    plan_path = str(row.get("plan_path") or "").strip()
    inline_plan = row.get("plan")
    if plan_path:
        p = Path(plan_path)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if not p.exists():
            return {"ok": False, "error": "plan_path_not_found", "plan_path": str(p)}
        rep = plan_schema.load_plan_from_path(str(p))
        if bool(rep.get("ok")):
            return {"ok": True, "plan": rep.get("plan"), "plan_path": str(p)}
        return {
            "ok": False,
            "error": str(rep.get("error") or "plan_path_invalid"),
            "detail": str((rep.get("details") or [{}])[0].get("message") if rep.get("details") else ""),
            "details": list(rep.get("details") or []),
            "plan_path": str(p),
        }
    if inline_plan is None:
        return {"ok": False, "error": "plan_missing"}
    rep = plan_schema.normalize_plan(inline_plan if not isinstance(inline_plan, list) else {"steps": inline_plan})
    if bool(rep.get("ok")):
        return {"ok": True, "plan": rep.get("plan"), "plan_path": ""}
    return {"ok": True, "plan": inline_plan, "plan_path": "", "warnings": ["plan_lenient_mode"]}


__all__ = [
    "queue_path",
    "events",
    "append_event",
    "enqueue",
    "claim",
    "start",
    "done",
    "fail",
    "cancel",
    "approve",
    "cancel_for_agent",
    "expire",
    "fold_state",
    "select_next",
    "list_queue",
    "load_plan",
]
