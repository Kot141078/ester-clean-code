# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_LOCK = threading.RLock()


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _windows_dir() -> Path:
    p = (_persist_dir() / "windows").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _state_path() -> Path:
    return (_windows_dir() / "execution_window_state.json").resolve()


def _events_path() -> Path:
    p = (_windows_dir() / "execution_window.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def _now_ts() -> int:
    return int(time.time())


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()


def _default_budgets() -> Dict[str, int]:
    ttl = max(1, int(os.getenv("ESTER_EXECUTION_TTL_SEC", "600") or "600"))
    return {
        "ttl_sec": ttl,
        "budget_seconds": max(1, int(os.getenv("ESTER_EXECUTION_BUDGET_SECONDS", str(ttl)) or str(ttl))),
        "budget_energy": max(1, int(os.getenv("ESTER_EXECUTION_BUDGET_ENERGY", "100") or "100")),
    }


def _default_usage() -> Dict[str, int]:
    return {
        "seconds_used": 0,
        "energy_used": 0,
        "ticks_total": 0,
    }


def _default_state() -> Dict[str, Any]:
    return {
        "open": False,
        "window_id": "",
        "opened_ts": 0,
        "expires_ts": 0,
        "actor": "",
        "reason": "",
        "meta": {},
        "budgets": _default_budgets(),
        "usage": _default_usage(),
        "updated_ts": _now_ts(),
    }


def _normalize_budgets(
    raw: Any,
    *,
    ttl_sec: Optional[int] = None,
    budget_seconds: Optional[int] = None,
    budget_energy: Optional[int] = None,
) -> Dict[str, int]:
    src = dict(raw or {})
    if ttl_sec is not None:
        src["ttl_sec"] = ttl_sec
    if budget_seconds is not None:
        src["budget_seconds"] = budget_seconds
    if budget_energy is not None:
        src["budget_energy"] = budget_energy

    base = _default_budgets()
    out = {
        "ttl_sec": int(src.get("ttl_sec") or base["ttl_sec"]),
        "budget_seconds": int(src.get("budget_seconds") or base["budget_seconds"]),
        "budget_energy": int(src.get("budget_energy") or base["budget_energy"]),
    }
    out["ttl_sec"] = max(1, out["ttl_sec"])
    out["budget_seconds"] = max(1, out["budget_seconds"])
    out["budget_energy"] = max(1, out["budget_energy"])
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
        return _default_state()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("bad_state")
    except Exception:
        raw = _default_state()
    st = _default_state()
    st.update(raw)
    st["meta"] = dict(st.get("meta") or {})
    st["budgets"] = _normalize_budgets(st.get("budgets"))
    usage = dict(st.get("usage") or {})
    st["usage"] = {
        "seconds_used": max(0, int(usage.get("seconds_used") or 0)),
        "energy_used": max(0, int(usage.get("energy_used") or 0)),
        "ticks_total": max(0, int(usage.get("ticks_total") or 0)),
    }
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
    usage: Dict[str, Any],
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    _append_jsonl(
        _events_path(),
        {
            "ts": _now_ts(),
            "event": str(event or "").strip(),
            "window_id": str(window_id or "").strip(),
            "actor": str(actor or "").strip(),
            "reason": str(reason or "").strip(),
            "budgets": dict(budgets or {}),
            "usage": dict(usage or {}),
            "meta": dict(meta or {}),
        },
    )


def _refresh_expired_locked(st: Dict[str, Any], now: int) -> Dict[str, Any]:
    if bool(st.get("open")) and int(st.get("expires_ts") or 0) <= now:
        _window_event(
            event="expire",
            window_id=str(st.get("window_id") or ""),
            actor=str(st.get("actor") or "system"),
            reason="ttl_expired",
            budgets=dict(st.get("budgets") or {}),
            usage=dict(st.get("usage") or {}),
            meta=dict(st.get("meta") or {}),
        )
        st["open"] = False
        st["window_id"] = ""
        st["expires_ts"] = 0
        st["reason"] = ""
    return st


def _budgets_left(st: Dict[str, Any], now_ts: Optional[int] = None) -> Dict[str, int]:
    now = int(now_ts if now_ts is not None else _now_ts())
    budgets = dict(st.get("budgets") or {})
    usage = dict(st.get("usage") or {})
    return {
        "ttl_remaining": max(0, int(st.get("expires_ts") or 0) - now),
        "budget_seconds_left": max(0, int(budgets.get("budget_seconds") or 0) - int(usage.get("seconds_used") or 0)),
        "budget_energy_left": max(0, int(budgets.get("budget_energy") or 0) - int(usage.get("energy_used") or 0)),
    }


def open_window(
    *,
    actor: str = "ester",
    reason: str = "",
    ttl_sec: Optional[int] = None,
    budget_seconds: Optional[int] = None,
    budget_energy: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = _now_ts()
    clean_actor = str(actor or "ester").strip() or "ester"
    clean_reason = str(reason or "").strip()
    clean_actor_low = clean_actor.lower()
    budgets = _normalize_budgets(
        {},
        ttl_sec=ttl_sec,
        budget_seconds=budget_seconds,
        budget_energy=budget_energy,
    )

    if clean_actor_low == "agent" or clean_actor_low.startswith("agent:"):
        _window_event(
            event="deny_open",
            window_id="",
            actor=clean_actor,
            reason="actor_forbidden",
            budgets=budgets,
            usage={},
            meta=dict(meta or {}),
        )
        return {"ok": False, "error": "actor_forbidden"}
    if not clean_reason:
        _window_event(
            event="deny_open",
            window_id="",
            actor=clean_actor,
            reason="reason_required",
            budgets=budgets,
            usage={},
            meta=dict(meta or {}),
        )
        return {"ok": False, "error": "reason_required"}

    window_id = "ew_" + uuid.uuid4().hex[:12]
    expires_ts = now + int(budgets.get("ttl_sec") or 0)
    usage = _default_usage()
    with _LOCK:
        st = _load_state()
        st = _refresh_expired_locked(st, now)
        st["open"] = True
        st["window_id"] = window_id
        st["opened_ts"] = now
        st["expires_ts"] = expires_ts
        st["actor"] = clean_actor
        st["reason"] = clean_reason
        st["meta"] = dict(meta or {})
        st["budgets"] = budgets
        st["usage"] = usage
        _save_state(st)
        _window_event(
            event="open",
            window_id=window_id,
            actor=clean_actor,
            reason=clean_reason,
            budgets=budgets,
            usage=usage,
            meta=dict(meta or {}),
        )

    return {
        "ok": True,
        "window_id": window_id,
        "expires_ts": expires_ts,
        "expires_at": _iso(expires_ts),
        "budgets": budgets,
    }


def close_window(window_id: str, *, actor: str = "ester", reason: str = "") -> Dict[str, Any]:
    wid = str(window_id or "").strip()
    if not wid:
        return {"ok": False, "error": "window_id_required"}
    now = _now_ts()
    with _LOCK:
        st = _load_state()
        st = _refresh_expired_locked(st, now)
        if not bool(st.get("open")) or str(st.get("window_id") or "") != wid:
            return {"ok": False, "error": "window_not_found", "window_id": wid}
        budgets = dict(st.get("budgets") or {})
        usage = dict(st.get("usage") or {})
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
            budgets=budgets,
            usage=usage,
            meta=meta,
        )
    return {"ok": True, "window_id": wid}


def note_usage(window_id: str, *, used_seconds: int = 0, used_energy: int = 0) -> Dict[str, Any]:
    wid = str(window_id or "").strip()
    now = _now_ts()
    with _LOCK:
        st = _load_state()
        st = _refresh_expired_locked(st, now)
        open_now = bool(st.get("open"))
        active_wid = str(st.get("window_id") or "")
        if (not open_now) or (not wid) or (wid != active_wid):
            left = _budgets_left(st, now)
            return {"ok": False, "error": "window_not_open", "window_id": wid, "budgets_left": left}
        usage = dict(st.get("usage") or {})
        usage["seconds_used"] = max(0, int(usage.get("seconds_used") or 0) + max(0, int(used_seconds or 0)))
        usage["energy_used"] = max(0, int(usage.get("energy_used") or 0) + max(0, int(used_energy or 0)))
        usage["ticks_total"] = max(0, int(usage.get("ticks_total") or 0) + 1)
        st["usage"] = usage
        _save_state(st)
        left = _budgets_left(st, now)
        return {"ok": True, "window_id": wid, "usage": usage, "budgets_left": left}


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
            "remaining_sec": int(left.get("ttl_remaining") or 0) if open_now else 0,
            "expires_ts": int(st.get("expires_ts") or 0),
            "expires_at": (_iso(int(st.get("expires_ts") or now)) if open_now else None),
            "actor": str(st.get("actor") or ""),
            "reason": str(st.get("reason") or ""),
            "budgets": dict(st.get("budgets") or {}),
            "budgets_left": left,
            "usage": dict(st.get("usage") or {}),
            "meta": dict(st.get("meta") or {}),
        }


def status() -> Dict[str, Any]:
    return current_window()


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
            "usage": dict(cur.get("usage") or {}),
            "meta": dict(cur.get("meta") or {}),
        }
        return {"ok": True, "count": 1, "windows": [row]}
    return {"ok": True, "count": 0, "windows": []}


def windows_path() -> Path:
    return _events_path()


__all__ = [
    "open_window",
    "close_window",
    "note_usage",
    "is_open",
    "current_window",
    "status",
    "list_windows",
    "windows_path",
]
