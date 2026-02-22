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


def _persist_dir(create: bool = True) -> Path:
    raw = str(os.getenv("PERSIST_DIR") or "").strip()
    if not raw:
        raw = str((Path.cwd() / "data").resolve())
    p = Path(raw).resolve()
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def _state_path(create: bool = True) -> Path:
    raw = str(os.getenv("ESTER_AGENT_CREATE_APPROVAL_PATH") or "").strip()
    if raw:
        p = Path(raw).resolve()
    else:
        p = (_persist_dir(create=create) / "proactivity" / "agent_create_approval.json").resolve()
    if create:
        p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> Dict[str, Any]:
    return {"requests": []}


def _load_state_no_lock(create: bool = True) -> Dict[str, Any]:
    p = _state_path(create=create)
    if not p.exists():
        return _default_state()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("bad_state")
    except Exception:
        raw = _default_state()
    reqs = list(raw.get("requests") or [])
    out_reqs: List[Dict[str, Any]] = []
    for row in reqs:
        if isinstance(row, dict):
            out_reqs.append(_normalize_request(row))
    return {"requests": out_reqs}


def _save_state_no_lock(state: Dict[str, Any]) -> None:
    p = _state_path(create=True)
    payload = json.dumps(dict(state or {}), ensure_ascii=False, indent=2)
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(p)
        return
    except Exception:
        pass
    p.write_text(payload, encoding="utf-8")


def _normalize_request(row: Dict[str, Any]) -> Dict[str, Any]:
    now_ts = int(time.time())
    out = {
        "id": str(row.get("id") or ("acreq_" + uuid.uuid4().hex[:12])),
        "ts": int(row.get("ts") or now_ts),
        "updated_ts": int(row.get("updated_ts") or row.get("ts") or now_ts),
        "status": str(row.get("status") or "pending"),
        "source": str(row.get("source") or ""),
        "template_id": str(row.get("template_id") or ""),
        "name": str(row.get("name") or ""),
        "goal": str(row.get("goal") or ""),
        "overrides": dict(row.get("overrides") or {}),
        "meta": dict(row.get("meta") or {}),
        "dedupe_key": str(row.get("dedupe_key") or ""),
        "approved_by": str(row.get("approved_by") or ""),
        "approved_ts": int(row.get("approved_ts") or 0),
        "denied_by": str(row.get("denied_by") or ""),
        "denied_ts": int(row.get("denied_ts") or 0),
        "done_by": str(row.get("done_by") or ""),
        "done_ts": int(row.get("done_ts") or 0),
        "agent_id": str(row.get("agent_id") or ""),
        "error": str(row.get("error") or ""),
        "note": str(row.get("note") or ""),
    }
    return out


def _find_request_mut(state: Dict[str, Any], request_id: str) -> Optional[Dict[str, Any]]:
    rid = str(request_id or "").strip()
    if not rid:
        return None
    for row in list(state.get("requests") or []):
        if str((row or {}).get("id") or "") == rid and isinstance(row, dict):
            return row
    return None


def request(
    *,
    source: str,
    template_id: str,
    name: str,
    goal: str,
    overrides: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
    dedupe_key: str = "",
    dedupe_ttl_sec: Optional[int] = None,
) -> Dict[str, Any]:
    now_ts = int(time.time())
    ttl = int(dedupe_ttl_sec if dedupe_ttl_sec is not None else int(os.getenv("ESTER_AGENT_CREATE_APPROVAL_DEDUPE_SEC", "900") or 900))
    ttl = max(0, ttl)
    key = str(dedupe_key or "").strip()
    with _LOCK:
        st = _load_state_no_lock(create=True)
        reqs = list(st.get("requests") or [])
        if key and ttl > 0:
            for row in reversed(reqs):
                r = _normalize_request(dict(row or {}))
                if str(r.get("status") or "") != "pending":
                    continue
                if str(r.get("dedupe_key") or "") != key:
                    continue
                if (now_ts - int(r.get("ts") or 0)) > ttl:
                    continue
                return {"ok": True, "created": False, "request": r}

        item = _normalize_request(
            {
                "id": "acreq_" + uuid.uuid4().hex[:12],
                "ts": now_ts,
                "updated_ts": now_ts,
                "status": "pending",
                "source": str(source or ""),
                "template_id": str(template_id or ""),
                "name": str(name or ""),
                "goal": str(goal or ""),
                "overrides": dict(overrides or {}),
                "meta": dict(meta or {}),
                "dedupe_key": key,
            }
        )
        reqs.append(item)
        st["requests"] = reqs[-2000:]
        _save_state_no_lock(st)
    return {"ok": True, "created": True, "request": item}


def list_pending(*, limit: int = 20) -> Dict[str, Any]:
    lim = max(1, int(limit or 20))
    with _LOCK:
        st = _load_state_no_lock(create=True)
        out = [
            _normalize_request(dict(row or {}))
            for row in list(st.get("requests") or [])
            if str((row or {}).get("status") or "pending") == "pending"
        ]
    out.sort(key=lambda r: int(r.get("ts") or 0))
    return {"ok": True, "total": len(out), "items": out[:lim]}


def get_request(request_id: str) -> Dict[str, Any]:
    rid = str(request_id or "").strip()
    if not rid:
        return {"ok": False, "error": "request_id_required"}
    with _LOCK:
        st = _load_state_no_lock(create=True)
        row = _find_request_mut(st, rid)
        if not row:
            return {"ok": False, "error": "request_not_found", "request_id": rid}
        item = _normalize_request(dict(row or {}))
    return {"ok": True, "request": item}


def approve(request_id: str, *, actor: str = "ester", note: str = "") -> Dict[str, Any]:
    rid = str(request_id or "").strip()
    if not rid:
        return {"ok": False, "error": "request_id_required"}
    now_ts = int(time.time())
    with _LOCK:
        st = _load_state_no_lock(create=True)
        row = _find_request_mut(st, rid)
        if not row:
            return {"ok": False, "error": "request_not_found", "request_id": rid}
        item = _normalize_request(dict(row or {}))
        status = str(item.get("status") or "")
        if status == "approved":
            return {"ok": True, "idempotent": True, "request": item}
        if status != "pending":
            return {"ok": False, "error": "not_pending", "request_id": rid, "status": status}
        row["status"] = "approved"
        row["approved_by"] = str(actor or "")
        row["approved_ts"] = now_ts
        row["updated_ts"] = now_ts
        if note:
            row["note"] = str(note)
        _save_state_no_lock(st)
        updated = _normalize_request(dict(row or {}))
    return {"ok": True, "request": updated}


def deny(request_id: str, *, actor: str = "ester", note: str = "") -> Dict[str, Any]:
    rid = str(request_id or "").strip()
    if not rid:
        return {"ok": False, "error": "request_id_required"}
    now_ts = int(time.time())
    with _LOCK:
        st = _load_state_no_lock(create=True)
        row = _find_request_mut(st, rid)
        if not row:
            return {"ok": False, "error": "request_not_found", "request_id": rid}
        item = _normalize_request(dict(row or {}))
        status = str(item.get("status") or "")
        if status == "denied":
            return {"ok": True, "idempotent": True, "request": item}
        if status not in {"pending", "approved"}:
            return {"ok": False, "error": "not_deniable", "request_id": rid, "status": status}
        row["status"] = "denied"
        row["denied_by"] = str(actor or "")
        row["denied_ts"] = now_ts
        row["updated_ts"] = now_ts
        if note:
            row["note"] = str(note)
        _save_state_no_lock(st)
        updated = _normalize_request(dict(row or {}))
    return {"ok": True, "request": updated}


def complete(request_id: str, *, actor: str = "ester", agent_id: str = "", note: str = "") -> Dict[str, Any]:
    rid = str(request_id or "").strip()
    if not rid:
        return {"ok": False, "error": "request_id_required"}
    now_ts = int(time.time())
    with _LOCK:
        st = _load_state_no_lock(create=True)
        row = _find_request_mut(st, rid)
        if not row:
            return {"ok": False, "error": "request_not_found", "request_id": rid}
        item = _normalize_request(dict(row or {}))
        status = str(item.get("status") or "")
        if status == "done":
            return {"ok": True, "idempotent": True, "request": item}
        if status not in {"approved", "pending"}:
            return {"ok": False, "error": "not_completable", "request_id": rid, "status": status}
        row["status"] = "done"
        row["done_by"] = str(actor or "")
        row["done_ts"] = now_ts
        row["updated_ts"] = now_ts
        if agent_id:
            row["agent_id"] = str(agent_id)
        if note:
            row["note"] = str(note)
        _save_state_no_lock(st)
        updated = _normalize_request(dict(row or {}))
    return {"ok": True, "request": updated}


def fail(request_id: str, *, actor: str = "ester", error: str = "", note: str = "") -> Dict[str, Any]:
    rid = str(request_id or "").strip()
    if not rid:
        return {"ok": False, "error": "request_id_required"}
    now_ts = int(time.time())
    with _LOCK:
        st = _load_state_no_lock(create=True)
        row = _find_request_mut(st, rid)
        if not row:
            return {"ok": False, "error": "request_not_found", "request_id": rid}
        row["status"] = "failed"
        row["done_by"] = str(actor or "")
        row["done_ts"] = now_ts
        row["updated_ts"] = now_ts
        row["error"] = str(error or "create_failed")
        if note:
            row["note"] = str(note)
        _save_state_no_lock(st)
        updated = _normalize_request(dict(row or {}))
    return {"ok": True, "request": updated}


__all__ = [
    "request",
    "list_pending",
    "get_request",
    "approve",
    "deny",
    "complete",
    "fail",
]

