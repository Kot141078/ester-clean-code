# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOCK = threading.RLock()
_DEFAULT_HOSTS = ["api.telegram.org"]


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _state_path() -> Path:
    p = (_persist_dir() / "runtime" / "comm_windows.json").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        try:
            p.write_text(json.dumps({"windows": {}, "updated_ts": int(time.time())}, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    return p


def _load_state() -> Dict[str, Any]:
    p = _state_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("bad_state")
    except Exception:
        raw = {"windows": {}, "updated_ts": int(time.time())}
    raw.setdefault("windows", {})
    if not isinstance(raw["windows"], dict):
        raw["windows"] = {}
    raw.setdefault("updated_ts", int(time.time()))
    return raw


def _save_state(state: Dict[str, Any]) -> None:
    p = _state_path()
    payload = json.dumps(dict(state or {}), ensure_ascii=False, indent=2)
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(p)
        return
    except Exception:
        pass
    try:
        p.write_text(payload, encoding="utf-8")
    except Exception:
        return


def _clean_hosts(hosts: Optional[List[str]]) -> List[str]:
    out: List[str] = []
    for h in list(hosts or []):
        s = str(h or "").strip().lower()
        if not s or "/" in s or ":" in s:
            continue
        if s not in out:
            out.append(s)
    return out


def _cleanup_expired(state: Dict[str, Any], now_ts: Optional[int] = None) -> Dict[str, Any]:
    now = int(now_ts if now_ts is not None else time.time())
    wins = dict(state.get("windows") or {})
    keep: Dict[str, Any] = {}
    for wid, row in wins.items():
        exp = int((row or {}).get("expires_ts") or 0)
        if exp > now and not bool((row or {}).get("closed")):
            keep[str(wid)] = dict(row or {})
    state["windows"] = keep
    state["updated_ts"] = now
    return state


def open_window(
    kind: str = "telegram",
    ttl_sec: int = 60,
    reason: str = "",
    allow_hosts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    now = int(time.time())
    ttl = max(1, int(ttl_sec or 60))
    hosts = _clean_hosts(allow_hosts) or list(_DEFAULT_HOSTS)
    wid = "cw_" + uuid.uuid4().hex[:12]
    row = {
        "id": wid,
        "kind": str(kind or "telegram").strip().lower() or "telegram",
        "created_ts": now,
        "expires_ts": now + ttl,
        "ttl_sec": ttl,
        "reason": str(reason or "").strip(),
        "allow_hosts": hosts,
        "closed": False,
    }
    with _LOCK:
        st = _cleanup_expired(_load_state(), now)
        win = dict(st.get("windows") or {})
        win[wid] = row
        st["windows"] = win
        st["updated_ts"] = now
        _save_state(st)
    return {"ok": True, "window_id": wid, "window": row}


def is_open(window_id: str) -> Dict[str, Any]:
    wid = str(window_id or "").strip()
    if not wid:
        return {"ok": False, "open": False, "error": "window_id_required"}
    now = int(time.time())
    with _LOCK:
        st = _cleanup_expired(_load_state(), now)
        _save_state(st)
        row = dict((st.get("windows") or {}).get(wid) or {})
    if not row:
        return {"ok": True, "open": False, "remaining": 0, "window_id": wid}
    rem = max(0, int(row.get("expires_ts") or 0) - now)
    return {"ok": True, "open": rem > 0, "remaining": rem, "window_id": wid, "window": row}


def close_window(window_id: str) -> Dict[str, Any]:
    wid = str(window_id or "").strip()
    if not wid:
        return {"ok": False, "error": "window_id_required"}
    now = int(time.time())
    with _LOCK:
        st = _load_state()
        win = dict(st.get("windows") or {})
        row = dict(win.get(wid) or {})
        if not row:
            return {"ok": False, "error": "window_not_found", "window_id": wid}
        row["closed"] = True
        row["closed_ts"] = now
        win[wid] = row
        st["windows"] = win
        st["updated_ts"] = now
        _save_state(st)
    return {"ok": True, "window_id": wid, "closed": True}


def list_windows() -> Dict[str, Any]:
    now = int(time.time())
    with _LOCK:
        st = _cleanup_expired(_load_state(), now)
        _save_state(st)
        rows = [dict(v) for _, v in sorted((st.get("windows") or {}).items())]
    return {"ok": True, "count": len(rows), "windows": rows}


__all__ = ["open_window", "is_open", "close_window", "list_windows"]

