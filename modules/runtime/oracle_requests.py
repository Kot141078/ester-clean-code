# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.runtime import oracle_window

_LOCK = threading.RLock()


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    out = Path(root).resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _oracle_dir() -> Path:
    out = (_persist_dir() / "oracle").resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _requests_path() -> Path:
    p = (_oracle_dir() / "requests.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def _state_path() -> Path:
    return (_oracle_dir() / "requests_state.json").resolve()


def _now_ts() -> int:
    return int(time.time())


def _request_ttl_sec() -> int:
    try:
        return max(60, int(os.getenv("ESTER_ORACLE_REQUEST_TTL_SEC", "3600") or "3600"))
    except Exception:
        return 3600


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    text = json.dumps(dict(payload or {}), ensure_ascii=False, indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
        return
    except Exception:
        pass
    path.write_text(text, encoding="utf-8")


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(dict(row or {}), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _read_rows() -> List[Dict[str, Any]]:
    path = _requests_path()
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            if isinstance(obj, dict):
                out.append(obj)
    return out


def _build_latest(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        rid = str(row.get("request_id") or "").strip()
        if not rid:
            continue
        latest[rid] = dict(row)
    return latest


def _save_state(latest: Dict[str, Dict[str, Any]]) -> None:
    _atomic_write_json(
        _state_path(),
        {
            "updated_ts": _now_ts(),
            "total": len(latest),
            "requests": latest,
        },
    )


def _record(
    *,
    request_id: str,
    ts: int,
    agent_id: str,
    plan_id: str,
    step_index: Optional[int],
    action_id: str,
    model: str,
    purpose: str,
    prompt_hash: str,
    budgets_requested: Dict[str, Any],
    status: str,
    approved_by: str = "",
    approved_ts: Optional[int] = None,
    window_id: str = "",
    deny_reason: str = "",
) -> Dict[str, Any]:
    return {
        "request_id": str(request_id or "").strip(),
        "ts": int(ts),
        "agent_id": str(agent_id or "").strip(),
        "plan_id": str(plan_id or "").strip(),
        "step_index": (None if step_index is None else int(step_index)),
        "action_id": str(action_id or "").strip(),
        "model": str(model or "").strip(),
        "purpose": str(purpose or "").strip(),
        "prompt_hash": str(prompt_hash or "").strip(),
        "budgets_requested": dict(budgets_requested or {}),
        "status": str(status or "").strip(),
        "approved_by": str(approved_by or "").strip(),
        "approved_ts": (None if approved_ts is None else int(approved_ts)),
        "window_id": str(window_id or "").strip(),
        "deny_reason": str(deny_reason or "").strip(),
    }


def _append_request(row: Dict[str, Any]) -> Dict[str, Any]:
    with _LOCK:
        _append_jsonl(_requests_path(), row)
        latest = _build_latest(_read_rows())
        _save_state(latest)
    return row


def submit_request(
    *,
    agent_id: str,
    plan_id: str,
    step_index: Optional[int],
    action_id: str,
    model: str,
    purpose: str,
    prompt_digest: str,
    budgets_requested: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ts = _now_ts()
    rid = "orq_" + uuid.uuid4().hex[:12]
    row = _record(
        request_id=rid,
        ts=ts,
        agent_id=str(agent_id or ""),
        plan_id=str(plan_id or ""),
        step_index=step_index,
        action_id=str(action_id or "llm.remote.call"),
        model=str(model or ""),
        purpose=str(purpose or ""),
        prompt_hash=str(prompt_digest or ""),
        budgets_requested=dict(budgets_requested or {}),
        status="pending",
    )
    _append_request(row)
    return {"ok": True, "request_id": rid, "status": "pending", "request": row}


def _expire_pending_locked(latest: Dict[str, Dict[str, Any]], now_ts: int) -> int:
    ttl = _request_ttl_sec()
    expired = 0
    for rid, row in list(latest.items()):
        if str((row or {}).get("status") or "") != "pending":
            continue
        ts = int((row or {}).get("ts") or 0)
        if ts <= 0:
            continue
        if (now_ts - ts) < ttl:
            continue
        expired_row = _record(
            request_id=rid,
            ts=now_ts,
            agent_id=str(row.get("agent_id") or ""),
            plan_id=str(row.get("plan_id") or ""),
            step_index=row.get("step_index"),
            action_id=str(row.get("action_id") or ""),
            model=str(row.get("model") or ""),
            purpose=str(row.get("purpose") or ""),
            prompt_hash=str(row.get("prompt_hash") or ""),
            budgets_requested=dict(row.get("budgets_requested") or {}),
            status="expired",
            approved_by="",
            approved_ts=None,
            window_id=str(row.get("window_id") or ""),
            deny_reason="request_ttl_expired",
        )
        _append_jsonl(_requests_path(), expired_row)
        latest[rid] = expired_row
        expired += 1
    return expired


def expire_requests(now_ts: Optional[int] = None) -> Dict[str, Any]:
    ts = int(now_ts if now_ts is not None else _now_ts())
    with _LOCK:
        rows = _read_rows()
        latest = _build_latest(rows)
        expired = _expire_pending_locked(latest, ts)
        if expired:
            _save_state(latest)
        return {"ok": True, "expired": expired}


def _latest_map() -> Dict[str, Dict[str, Any]]:
    expire_requests()
    with _LOCK:
        return _build_latest(_read_rows())


def get_request(request_id: str) -> Dict[str, Any]:
    rid = str(request_id or "").strip()
    if not rid:
        return {"ok": False, "error": "request_id_required"}
    latest = _latest_map()
    row = dict(latest.get(rid) or {})
    if not row:
        return {"ok": False, "error": "request_not_found", "request_id": rid}
    return {"ok": True, "request_id": rid, "request": row}


def list_requests(status: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    wanted = str(status or "").strip()
    latest = _latest_map()
    rows = [dict(v) for _, v in sorted(latest.items(), key=lambda kv: int((kv[1] or {}).get("ts") or 0), reverse=True)]
    if wanted:
        rows = [r for r in rows if str(r.get("status") or "") == wanted]
    rows = rows[: max(1, int(limit or 100))]
    return {"ok": True, "count": len(rows), "requests": rows}


def _ester_actor(actor: str) -> bool:
    clean = str(actor or "").strip().lower()
    return clean == "ester" or clean.startswith("ester:")


def approve_request(
    request_id: str,
    *,
    actor: str = "ester",
    reason: str = "",
    ttl_sec: Optional[int] = None,
    budgets: Optional[Dict[str, Any]] = None,
    allow_agents: bool = True,
) -> Dict[str, Any]:
    rid = str(request_id or "").strip()
    if not rid:
        return {"ok": False, "error": "request_id_required"}
    if not _ester_actor(actor):
        return {"ok": False, "error": "actor_forbidden", "actor": str(actor or "")}

    req_rep = get_request(rid)
    if not req_rep.get("ok"):
        return req_rep
    req = dict(req_rep.get("request") or {})
    if str(req.get("status") or "") != "pending":
        return {"ok": False, "error": "request_not_pending", "request_id": rid, "status": str(req.get("status") or "")}

    b = dict(budgets or {})
    if ttl_sec is not None:
        b["ttl_sec"] = int(ttl_sec)
    open_rep = oracle_window.open_window(
        reason=str(reason or req.get("purpose") or "oracle_request_approved"),
        actor=str(actor or "ester"),
        budgets=b,
        allow_agents=bool(allow_agents),
        meta={
            "approved_request_ids": [rid],
            "approved_agents": [str(req.get("agent_id") or "")] if str(req.get("agent_id") or "").strip() else [],
            "approved_plan_id": str(req.get("plan_id") or ""),
            "approved_step_index": req.get("step_index"),
        },
    )
    if not bool(open_rep.get("ok")):
        return {"ok": False, "error": "window_open_failed", "detail": open_rep}

    ts = _now_ts()
    row = _record(
        request_id=rid,
        ts=ts,
        agent_id=str(req.get("agent_id") or ""),
        plan_id=str(req.get("plan_id") or ""),
        step_index=req.get("step_index"),
        action_id=str(req.get("action_id") or ""),
        model=str(req.get("model") or ""),
        purpose=str(req.get("purpose") or ""),
        prompt_hash=str(req.get("prompt_hash") or ""),
        budgets_requested=dict(req.get("budgets_requested") or {}),
        status="approved",
        approved_by=str(actor or "ester"),
        approved_ts=ts,
        window_id=str(open_rep.get("window_id") or ""),
        deny_reason="",
    )
    _append_request(row)
    return {
        "ok": True,
        "request_id": rid,
        "window_id": str(open_rep.get("window_id") or ""),
        "approved_ts": ts,
        "request": row,
        "window": open_rep,
    }


def deny_request(request_id: str, *, actor: str = "ester", reason: str = "") -> Dict[str, Any]:
    rid = str(request_id or "").strip()
    if not rid:
        return {"ok": False, "error": "request_id_required"}
    if not _ester_actor(actor):
        return {"ok": False, "error": "actor_forbidden", "actor": str(actor or "")}
    req_rep = get_request(rid)
    if not req_rep.get("ok"):
        return req_rep
    req = dict(req_rep.get("request") or {})
    ts = _now_ts()
    row = _record(
        request_id=rid,
        ts=ts,
        agent_id=str(req.get("agent_id") or ""),
        plan_id=str(req.get("plan_id") or ""),
        step_index=req.get("step_index"),
        action_id=str(req.get("action_id") or ""),
        model=str(req.get("model") or ""),
        purpose=str(req.get("purpose") or ""),
        prompt_hash=str(req.get("prompt_hash") or ""),
        budgets_requested=dict(req.get("budgets_requested") or {}),
        status="denied",
        approved_by=str(actor or "ester"),
        approved_ts=ts,
        window_id=str(req.get("window_id") or ""),
        deny_reason=str(reason or "denied_by_ester"),
    )
    _append_request(row)
    return {"ok": True, "request_id": rid, "request": row}


def validate_approved_request(
    *,
    request_id: str,
    agent_id: str,
    plan_id: str,
    step_index: Optional[int],
    model: str,
    window_id: str,
) -> Dict[str, Any]:
    rep = get_request(request_id)
    if not rep.get("ok"):
        return {"ok": False, "error": "oracle_not_approved", "policy_hit": "request_not_found"}
    req = dict(rep.get("request") or {})
    if str(req.get("status") or "") != "approved":
        return {"ok": False, "error": "oracle_not_approved", "policy_hit": "request_not_approved"}
    if str(agent_id or "").strip() and str(req.get("agent_id") or "").strip() != str(agent_id).strip():
        return {"ok": False, "error": "request_mismatch", "policy_hit": "request_agent_mismatch"}
    if str(plan_id or "").strip() and str(req.get("plan_id") or "").strip() not in {"", str(plan_id).strip()}:
        return {"ok": False, "error": "request_mismatch", "policy_hit": "request_plan_mismatch"}
    req_step = req.get("step_index")
    if step_index is not None and req_step is not None:
        try:
            if int(req_step) != int(step_index):
                return {"ok": False, "error": "request_mismatch", "policy_hit": "request_step_mismatch"}
        except Exception:
            return {"ok": False, "error": "request_mismatch", "policy_hit": "request_step_mismatch"}
    req_model = str(req.get("model") or "").strip()
    if req_model and str(model or "").strip() and req_model != str(model).strip():
        return {"ok": False, "error": "request_mismatch", "policy_hit": "request_model_mismatch"}
    req_window = str(req.get("window_id") or "").strip()
    if req_window and str(window_id or "").strip() and req_window != str(window_id).strip():
        return {"ok": False, "error": "request_mismatch", "policy_hit": "request_window_mismatch"}
    return {"ok": True, "request": req}


def summary() -> Dict[str, Any]:
    latest = _latest_map()
    pending_count = 0
    approved_count_recent = 0
    last_request_id = ""
    last_approved_id = ""
    last_request_ts = 0
    last_approved_ts = 0
    now = _now_ts()
    for rid, row in latest.items():
        status = str(row.get("status") or "")
        ts = int(row.get("ts") or 0)
        if ts > last_request_ts:
            last_request_ts = ts
            last_request_id = rid
        if status == "pending":
            pending_count += 1
        if status == "approved":
            approved_ts = int(row.get("approved_ts") or ts or 0)
            if (now - approved_ts) <= 3600:
                approved_count_recent += 1
            if approved_ts > last_approved_ts:
                last_approved_ts = approved_ts
                last_approved_id = rid
    return {
        "ok": True,
        "pending_count": pending_count,
        "approved_count_recent": approved_count_recent,
        "last_request_id": last_request_id,
        "last_approved_id": last_approved_id,
    }


__all__ = [
    "submit_request",
    "list_requests",
    "get_request",
    "approve_request",
    "deny_request",
    "expire_requests",
    "validate_approved_request",
    "summary",
]
