# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def _state_path() -> Path:
    return (_oracle_dir() / "state.json").resolve()


def _windows_path() -> Path:
    p = (_oracle_dir() / "windows.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def _calls_path() -> Path:
    p = (_oracle_dir() / "calls.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def _now_ts() -> int:
    return int(time.time())


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()


def _default_budgets() -> Dict[str, int]:
    return {
        "ttl_sec": max(1, int(os.getenv("ESTER_ORACLE_TTL_SEC", "600") or "600")),
        "max_calls": max(1, int(os.getenv("ESTER_ORACLE_MAX_CALLS", "3") or "3")),
        "max_est_tokens_in_total": max(1, int(os.getenv("ESTER_ORACLE_MAX_TOKENS_IN", "8000") or "8000")),
        "max_tokens_out_total": max(1, int(os.getenv("ESTER_ORACLE_MAX_TOKENS_OUT", "2000") or "2000")),
        "max_wall_ms_per_call": max(100, int(os.getenv("ESTER_ORACLE_MAX_WALL_MS", "20000") or "20000")),
    }


def _default_usage() -> Dict[str, int]:
    return {
        "calls_total": 0,
        "est_tokens_in_total": 0,
        "tokens_out_total": 0,
    }


def _default_state() -> Dict[str, Any]:
    return {
        "open": False,
        "window_id": "",
        "opened_ts": 0,
        "expires_ts": 0,
        "actor": "",
        "reason": "",
        "allow_agents": False,
        "meta": {},
        "budgets": _default_budgets(),
        "usage": _default_usage(),
        "last_call": {"ts": None, "ok": None, "error": "", "window_id": ""},
        "updated_ts": _now_ts(),
    }


def _normalize_budgets(raw: Any, *, ttl_sec: Optional[int] = None) -> Dict[str, int]:
    src = dict(raw or {})
    base = _default_budgets()
    if ttl_sec is not None:
        src["ttl_sec"] = ttl_sec
    out = {
        "ttl_sec": int(src.get("ttl_sec") or base["ttl_sec"]),
        "max_calls": int(src.get("max_calls") or base["max_calls"]),
        "max_est_tokens_in_total": int(src.get("max_est_tokens_in_total") or src.get("max_tokens_in") or base["max_est_tokens_in_total"]),
        "max_tokens_out_total": int(src.get("max_tokens_out_total") or src.get("max_tokens_out") or base["max_tokens_out_total"]),
        "max_wall_ms_per_call": int(src.get("max_wall_ms_per_call") or base["max_wall_ms_per_call"]),
    }
    out["ttl_sec"] = max(1, out["ttl_sec"])
    out["max_calls"] = max(1, out["max_calls"])
    out["max_est_tokens_in_total"] = max(1, out["max_est_tokens_in_total"])
    out["max_tokens_out_total"] = max(1, out["max_tokens_out_total"])
    out["max_wall_ms_per_call"] = max(100, out["max_wall_ms_per_call"])
    return out


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


def _load_state() -> Dict[str, Any]:
    p = _state_path()
    if not p.exists():
        st = _default_state()
        _atomic_write_json(p, st)
        return st
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("bad_state")
    except Exception:
        raw = _default_state()
    st = _default_state()
    st.update(raw)
    st["budgets"] = _normalize_budgets(st.get("budgets"))
    usage = dict(st.get("usage") or {})
    st["usage"] = {
        "calls_total": max(0, int(usage.get("calls_total") or 0)),
        "est_tokens_in_total": max(0, int(usage.get("est_tokens_in_total") or 0)),
        "tokens_out_total": max(0, int(usage.get("tokens_out_total") or 0)),
    }
    st["meta"] = dict(st.get("meta") or {})
    st["updated_ts"] = int(st.get("updated_ts") or _now_ts())
    return st


def _save_state(st: Dict[str, Any]) -> None:
    payload = dict(st or {})
    payload["updated_ts"] = _now_ts()
    _atomic_write_json(_state_path(), payload)


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(dict(row or {}), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _window_event(
    *,
    event: str,
    window_id: str,
    actor: str,
    reason: str,
    budgets: Dict[str, Any],
    allow_agents: Any,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    _append_jsonl(
        _windows_path(),
        {
            "ts": _now_ts(),
            "event": str(event or "").strip(),
            "window_id": str(window_id or "").strip(),
            "actor": str(actor or "").strip(),
            "reason": str(reason or "").strip(),
            "budgets": dict(budgets or {}),
            "allow_agents": allow_agents,
            "meta": dict(meta or {}),
        },
    )


def _estimate_tokens_in(prompt: str) -> int:
    chars = len(str(prompt or ""))
    return max(1, (chars + 3) // 4)


def _budgets_left(st: Dict[str, Any], now_ts: Optional[int] = None) -> Dict[str, int]:
    now = int(now_ts if now_ts is not None else _now_ts())
    budgets = dict(st.get("budgets") or {})
    usage = dict(st.get("usage") or {})
    return {
        "remaining_calls": max(0, int(budgets.get("max_calls") or 0) - int(usage.get("calls_total") or 0)),
        "token_left_in": max(0, int(budgets.get("max_est_tokens_in_total") or 0) - int(usage.get("est_tokens_in_total") or 0)),
        "token_left_out": max(0, int(budgets.get("max_tokens_out_total") or 0) - int(usage.get("tokens_out_total") or 0)),
        "ttl_remaining": max(0, int(st.get("expires_ts") or 0) - now),
    }


def _refresh_expired_locked(st: Dict[str, Any], now: int) -> Dict[str, Any]:
    if bool(st.get("open")) and int(st.get("expires_ts") or 0) <= now:
        _window_event(
            event="expire",
            window_id=str(st.get("window_id") or ""),
            actor=str(st.get("actor") or "system"),
            reason="ttl_expired",
            budgets=dict(st.get("budgets") or {}),
            allow_agents=st.get("allow_agents"),
            meta=dict(st.get("meta") or {}),
        )
        st["open"] = False
        st["window_id"] = ""
        st["expires_ts"] = 0
        st["reason"] = ""
    return st


def _enabled() -> bool:
    return _truthy(os.getenv("ESTER_ORACLE_ENABLE", "0"))


def _deny_call_record(
    *,
    window_id: str,
    call_id: str,
    actor: str,
    agent_id: str,
    plan_id: str,
    step_index: Optional[int],
    model: str,
    prompt_digest: str,
    input_chars: int,
    est_tokens_in: int,
    max_tokens: int,
    error: str,
    policy_hit: str,
) -> Dict[str, Any]:
    return {
        "ts": _now_ts(),
        "window_id": str(window_id or ""),
        "call_id": str(call_id or ""),
        "actor": str(actor or ""),
        "agent_id": str(agent_id or ""),
        "plan_id": str(plan_id or ""),
        "step_index": (None if step_index is None else int(step_index)),
        "model": str(model or ""),
        "prompt_digest": str(prompt_digest or ""),
        "input_chars": int(input_chars),
        "est_tokens_in": int(est_tokens_in),
        "max_tokens": int(max_tokens),
        "ok": False,
        "latency_ms": 0,
        "tokens_out": 0,
        "error": str(error or ""),
        "policy_hit": str(policy_hit or ""),
    }


def open_window(
    reason: str = "",
    actor: str = "ester",
    budgets: Optional[Dict[str, Any]] = None,
    allow_agents: Any = False,
    meta: Optional[Dict[str, Any]] = None,
    *,
    ttl_sec: Optional[int] = None,
    kind: str = "openai",
    allow_hosts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    now = _now_ts()
    clean_reason = str(reason or "").strip()
    clean_actor = str(actor or "ester").strip() or "ester"
    clean_actor_low = clean_actor.lower()
    merged_meta = dict(meta or {})
    merged_meta.setdefault("kind", str(kind or "openai").strip().lower() or "openai")
    if allow_hosts is not None:
        merged_meta["allow_hosts"] = [str(x) for x in list(allow_hosts or []) if str(x).strip()]

    b = _normalize_budgets(budgets, ttl_sec=ttl_sec)
    if clean_actor_low == "agent" or clean_actor_low.startswith("agent:"):
        _window_event(
            event="deny_open",
            window_id="",
            actor=clean_actor,
            reason="actor_forbidden",
            budgets=b,
            allow_agents=allow_agents,
            meta=merged_meta,
        )
        return {"ok": False, "error": "actor_forbidden"}
    if not _enabled():
        _window_event(
            event="deny_open",
            window_id="",
            actor=clean_actor,
            reason="oracle_disabled",
            budgets=b,
            allow_agents=allow_agents,
            meta=merged_meta,
        )
        return {"ok": False, "error": "oracle_disabled"}
    if not clean_reason:
        _window_event(
            event="deny_open",
            window_id="",
            actor=clean_actor,
            reason="reason_required",
            budgets=b,
            allow_agents=allow_agents,
            meta=merged_meta,
        )
        return {"ok": False, "error": "reason_required"}

    window_id = "ow_" + uuid.uuid4().hex[:12]
    expires_ts = now + int(b["ttl_sec"])

    with _LOCK:
        st = _load_state()
        st = _refresh_expired_locked(st, now)
        st["open"] = True
        st["window_id"] = window_id
        st["opened_ts"] = now
        st["expires_ts"] = expires_ts
        st["actor"] = clean_actor
        st["reason"] = clean_reason
        st["allow_agents"] = allow_agents
        st["meta"] = merged_meta
        st["budgets"] = b
        st["usage"] = _default_usage()
        _save_state(st)
        _window_event(
            event="open",
            window_id=window_id,
            actor=clean_actor,
            reason=clean_reason,
            budgets=b,
            allow_agents=allow_agents,
            meta=merged_meta,
        )

    return {
        "ok": True,
        "window_id": window_id,
        "expires_ts": expires_ts,
        "expires_at": _iso(expires_ts),
        "budgets": b,
    }


def close_window(window_id: str, actor: str = "ester", reason: str = "") -> Dict[str, Any]:
    wid = str(window_id or "").strip()
    if not wid:
        return {"ok": False, "error": "window_id_required"}
    now = _now_ts()
    with _LOCK:
        st = _load_state()
        st = _refresh_expired_locked(st, now)
        if not bool(st.get("open")) or str(st.get("window_id") or "") != wid:
            return {"ok": False, "error": "window_not_found", "window_id": wid}
        b = dict(st.get("budgets") or {})
        allow_agents = st.get("allow_agents")
        meta = dict(st.get("meta") or {})
        st["open"] = False
        st["window_id"] = ""
        st["expires_ts"] = 0
        st["reason"] = ""
        _save_state(st)
        _window_event(
            event="close",
            window_id=wid,
            actor=str(actor or "ester"),
            reason=str(reason or ""),
            budgets=b,
            allow_agents=allow_agents,
            meta=meta,
        )
    return {"ok": True, "window_id": wid}


def current_window() -> Dict[str, Any]:
    now = _now_ts()
    with _LOCK:
        st = _load_state()
        st = _refresh_expired_locked(st, now)
        _save_state(st)
        open_now = bool(st.get("open"))
        wid = str(st.get("window_id") or "")
        left = _budgets_left(st, now)
        return {
            "ok": True,
            "open": open_now,
            "window_id": wid if open_now else "",
            "remaining_sec": int(left["ttl_remaining"]) if open_now else 0,
            "expires_ts": int(st.get("expires_ts") or 0),
            "expires_at": (_iso(int(st.get("expires_ts") or now)) if open_now else None),
            "actor": str(st.get("actor") or ""),
            "reason": str(st.get("reason") or ""),
            "allow_agents": st.get("allow_agents"),
            "budgets": dict(st.get("budgets") or {}),
            "budgets_left": left,
            "usage": dict(st.get("usage") or {}),
            "meta": dict(st.get("meta") or {}),
        }


def is_open(window_id: str = "") -> Dict[str, Any]:
    wid = str(window_id or "").strip()
    cur = current_window()
    open_now = bool(cur.get("open"))
    if wid and str(cur.get("window_id") or "") != wid:
        open_now = False
    out = dict(cur)
    out["open"] = bool(open_now)
    if not open_now:
        out["remaining_sec"] = 0
    return out


def authorize_call(
    *,
    window_id: str = "",
    actor: str = "",
    agent_id: str = "",
    plan_id: str = "",
    step_index: Optional[int] = None,
    model: str = "",
    prompt: str = "",
    max_tokens: int = 256,
    purpose: str = "",
    requested_wall_ms: int = 20000,
) -> Dict[str, Any]:
    now = _now_ts()
    call_id = "oc_" + uuid.uuid4().hex[:12]
    clean_model = str(model or "").strip()
    clean_actor = str(actor or "ester").strip() or "ester"
    prompt_text = str(prompt or "")
    digest = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    input_chars = len(prompt_text)
    est_tokens_in = _estimate_tokens_in(prompt_text)
    requested_tokens_out = max(1, int(max_tokens or 256))

    with _LOCK:
        st = _load_state()
        st = _refresh_expired_locked(st, now)
        _save_state(st)

        if not bool(st.get("open")):
            row = _deny_call_record(
                window_id="",
                call_id=call_id,
                actor=clean_actor,
                agent_id=str(agent_id or ""),
                plan_id=str(plan_id or ""),
                step_index=step_index,
                model=clean_model,
                prompt_digest=digest,
                input_chars=input_chars,
                est_tokens_in=est_tokens_in,
                max_tokens=requested_tokens_out,
                error="oracle_window_closed",
                policy_hit="oracle_window_closed",
            )
            _append_jsonl(_calls_path(), row)
            return {"ok": False, "error": "oracle_window_closed", "policy_hit": "oracle_window_closed", "call_id": call_id}

        active_wid = str(st.get("window_id") or "")
        if str(window_id or "").strip() and str(window_id).strip() != active_wid:
            row = _deny_call_record(
                window_id=active_wid,
                call_id=call_id,
                actor=clean_actor,
                agent_id=str(agent_id or ""),
                plan_id=str(plan_id or ""),
                step_index=step_index,
                model=clean_model,
                prompt_digest=digest,
                input_chars=input_chars,
                est_tokens_in=est_tokens_in,
                max_tokens=requested_tokens_out,
                error="oracle_window_mismatch",
                policy_hit="oracle_window_mismatch",
            )
            _append_jsonl(_calls_path(), row)
            return {"ok": False, "error": "oracle_window_mismatch", "policy_hit": "oracle_window_mismatch", "call_id": call_id}

        budgets = dict(st.get("budgets") or {})
        usage = dict(st.get("usage") or {})
        max_wall = int(budgets.get("max_wall_ms_per_call") or 20000)
        if int(requested_wall_ms or 0) > max_wall:
            row = _deny_call_record(
                window_id=active_wid,
                call_id=call_id,
                actor=clean_actor,
                agent_id=str(agent_id or ""),
                plan_id=str(plan_id or ""),
                step_index=step_index,
                model=clean_model,
                prompt_digest=digest,
                input_chars=input_chars,
                est_tokens_in=est_tokens_in,
                max_tokens=requested_tokens_out,
                error="oracle_budget_exceeded",
                policy_hit="oracle_budget_max_wall_ms_per_call",
            )
            _append_jsonl(_calls_path(), row)
            return {
                "ok": False,
                "error": "oracle_budget_exceeded",
                "policy_hit": "oracle_budget_max_wall_ms_per_call",
                "call_id": call_id,
                "window_id": active_wid,
            }

        projected_calls = int(usage.get("calls_total") or 0) + 1
        projected_in = int(usage.get("est_tokens_in_total") or 0) + est_tokens_in
        projected_out = int(usage.get("tokens_out_total") or 0) + requested_tokens_out

        if projected_calls > int(budgets.get("max_calls") or 0):
            policy_hit = "oracle_budget_max_calls"
        elif projected_in > int(budgets.get("max_est_tokens_in_total") or 0):
            policy_hit = "oracle_budget_max_est_tokens_in_total"
        elif projected_out > int(budgets.get("max_tokens_out_total") or 0):
            policy_hit = "oracle_budget_max_tokens_out_total"
        else:
            policy_hit = ""

        if policy_hit:
            row = _deny_call_record(
                window_id=active_wid,
                call_id=call_id,
                actor=clean_actor,
                agent_id=str(agent_id or ""),
                plan_id=str(plan_id or ""),
                step_index=step_index,
                model=clean_model,
                prompt_digest=digest,
                input_chars=input_chars,
                est_tokens_in=est_tokens_in,
                max_tokens=requested_tokens_out,
                error="oracle_budget_exceeded",
                policy_hit=policy_hit,
            )
            _append_jsonl(_calls_path(), row)
            return {
                "ok": False,
                "error": "oracle_budget_exceeded",
                "policy_hit": policy_hit,
                "call_id": call_id,
                "window_id": active_wid,
            }

        usage["calls_total"] = projected_calls
        usage["est_tokens_in_total"] = projected_in
        st["usage"] = usage
        _save_state(st)
        left = _budgets_left(st, now)

    return {
        "ok": True,
        "window_id": active_wid,
        "call_id": call_id,
        "prompt_digest": digest,
        "input_chars": input_chars,
        "est_tokens_in": est_tokens_in,
        "max_tokens": requested_tokens_out,
        "purpose": str(purpose or ""),
        "budgets_left": left,
        "max_wall_ms_per_call": max_wall,
    }


def note_call(window_id: str, call_record: Dict[str, Any]) -> Dict[str, Any]:
    wid = str(window_id or "").strip()
    row = dict(call_record or {})
    row.setdefault("ts", _now_ts())
    row.setdefault("window_id", wid)
    row.setdefault("call_id", "oc_" + uuid.uuid4().hex[:12])
    row.setdefault("ok", False)
    row.setdefault("latency_ms", 0)
    row.setdefault("tokens_out", 0)

    with _LOCK:
        st = _load_state()
        st = _refresh_expired_locked(st, _now_ts())
        usage = dict(st.get("usage") or {})
        if bool(row.get("ok")) and bool(st.get("open")) and str(st.get("window_id") or "") == wid:
            usage["tokens_out_total"] = max(0, int(usage.get("tokens_out_total") or 0) + max(0, int(row.get("tokens_out") or 0)))
            st["usage"] = usage
            _save_state(st)
        st["last_call"] = {
            "ts": int(row.get("ts") or _now_ts()),
            "ok": bool(row.get("ok")),
            "error": str(row.get("error") or ""),
            "window_id": str(row.get("window_id") or ""),
            "policy_hit": str(row.get("policy_hit") or ""),
        }
        _save_state(st)
        _append_jsonl(_calls_path(), row)
        left = _budgets_left(st)
    return {"ok": True, "window_id": wid, "budgets_left": left}


def list_windows() -> Dict[str, Any]:
    cur = current_window()
    if bool(cur.get("open")):
        row = {
            "id": str(cur.get("window_id") or ""),
            "window_id": str(cur.get("window_id") or ""),
            "created_ts": int(cur.get("expires_ts") or 0) - int((cur.get("budgets") or {}).get("ttl_sec") or 0),
            "expires_ts": int(cur.get("expires_ts") or 0),
            "remaining_sec": int(cur.get("remaining_sec") or 0),
            "reason": str(cur.get("reason") or ""),
            "actor": str(cur.get("actor") or ""),
            "budgets": dict(cur.get("budgets") or {}),
            "budgets_left": dict(cur.get("budgets_left") or {}),
            "allow_agents": cur.get("allow_agents"),
            "meta": dict(cur.get("meta") or {}),
        }
        return {"ok": True, "count": 1, "windows": [row]}
    return {"ok": True, "count": 0, "windows": []}


def calls_path() -> Path:
    return _calls_path()


def windows_path() -> Path:
    return _windows_path()


def last_call_status() -> Dict[str, Any]:
    st = _load_state()
    return dict(st.get("last_call") or {})


__all__ = [
    "open_window",
    "close_window",
    "is_open",
    "current_window",
    "authorize_call",
    "note_call",
    "list_windows",
    "calls_path",
    "windows_path",
    "last_call_status",
]
