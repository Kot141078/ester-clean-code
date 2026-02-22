# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

TICKET_EVENT_SCHEMA = "ester.curiosity.ticket_event.v1"
STATE_SCHEMA = "ester.curiosity.state.v1"
ALLOWED_SOURCES = {
    "dialog",
    "pending",
    "contradiction",
    "low_confidence",
    "memory_miss",
    "user",
}
ALLOWED_EVENTS = {"open", "plan", "enqueue", "resolve", "fail", "stale", "negative"}
_LOCK = threading.RLock()


def _persist_dir() -> Path:
    root = str(os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _curiosity_root() -> Path:
    p = (_persist_dir() / "curiosity").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def tickets_path() -> Path:
    p = (_curiosity_root() / "tickets.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def state_path() -> Path:
    p = (_curiosity_root() / "state.json").resolve()
    if not p.exists():
        payload = json.dumps(_default_state(), ensure_ascii=False, indent=2)
        p.write_text(payload, encoding="utf-8")
    return p


def _now_ts() -> int:
    return int(time.time())


def _safe_int(value: Any, default: int, *, min_value: int = 0) -> int:
    try:
        out = int(value)
    except Exception:
        out = int(default)
    return max(min_value, out)


def _safe_float(value: Any, default: float, *, min_value: float = 0.0, max_value: float = 1.0) -> float:
    try:
        out = float(value)
    except Exception:
        out = float(default)
    if out < min_value:
        out = min_value
    if out > max_value:
        out = max_value
    return out


def _normalize_source(source: str) -> str:
    src = str(source or "").strip().lower()
    return src if src in ALLOWED_SOURCES else "dialog"


def _sha256_hex(text: str) -> str:
    import hashlib

    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _default_budgets(raw: Optional[Dict[str, Any]]) -> Dict[str, int]:
    src = dict(raw or {})
    return {
        "max_depth": _safe_int(src.get("max_depth"), 2, min_value=1),
        "max_hops": _safe_int(src.get("max_hops"), 2, min_value=1),
        "max_docs": _safe_int(src.get("max_docs"), 12, min_value=1),
        "max_work_ms": _safe_int(src.get("max_work_ms"), 1500, min_value=100),
    }


def _default_state() -> Dict[str, Any]:
    return {
        "schema": STATE_SCHEMA,
        "updated_ts": 0,
        "last_ticket_ts": 0,
        "last_ticket_id": "",
        "last_error": "",
        "events_total": 0,
        "tickets_total": 0,
        "tickets_open": 0,
        "tickets_stale": 0,
        "tickets_resolved_24h": 0,
        "last_enqueue_ts": 0,
        "last_resolve_ts": 0,
        "by_event": {},
        "by_status": {},
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
    line = json.dumps(dict(row or {}), ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _load_state() -> Dict[str, Any]:
    p = (_curiosity_root() / "state.json").resolve()
    if not p.exists():
        p.write_text(json.dumps(_default_state(), ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("bad_state")
    except Exception:
        raw = _default_state()
    out = _default_state()
    out.update(raw)
    out["schema"] = STATE_SCHEMA
    out["updated_ts"] = _safe_int(out.get("updated_ts"), 0, min_value=0)
    out["last_ticket_ts"] = _safe_int(out.get("last_ticket_ts"), 0, min_value=0)
    out["last_ticket_id"] = str(out.get("last_ticket_id") or "")
    out["last_error"] = str(out.get("last_error") or "")
    out["events_total"] = _safe_int(out.get("events_total"), 0, min_value=0)
    out["tickets_total"] = _safe_int(out.get("tickets_total"), 0, min_value=0)
    out["tickets_open"] = _safe_int(out.get("tickets_open"), 0, min_value=0)
    out["tickets_stale"] = _safe_int(out.get("tickets_stale"), 0, min_value=0)
    out["tickets_resolved_24h"] = _safe_int(out.get("tickets_resolved_24h"), 0, min_value=0)
    out["last_enqueue_ts"] = _safe_int(out.get("last_enqueue_ts"), 0, min_value=0)
    out["last_resolve_ts"] = _safe_int(out.get("last_resolve_ts"), 0, min_value=0)
    if not isinstance(out.get("by_event"), dict):
        out["by_event"] = {}
    if not isinstance(out.get("by_status"), dict):
        out["by_status"] = {}
    return out


def _save_state(state: Dict[str, Any]) -> None:
    p = (_curiosity_root() / "state.json").resolve()
    payload = json.dumps(dict(state or {}), ensure_ascii=False, indent=2)
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(p)
        return
    except Exception:
        pass
    p.write_text(payload, encoding="utf-8")


def ticket_events() -> List[Dict[str, Any]]:
    with _LOCK:
        return _read_jsonl(tickets_path())


def fold_tickets() -> Dict[str, Any]:
    rows = ticket_events()
    tickets: Dict[str, Dict[str, Any]] = {}
    by_event: Dict[str, int] = {}
    for row in rows:
        event = str(row.get("event") or "").strip().lower()
        ticket_id = str(row.get("ticket_id") or "").strip()
        if not ticket_id:
            continue
        by_event[event] = int(by_event.get(event, 0)) + 1
        item = dict(tickets.get(ticket_id) or {})
        if not item:
            item = {
                "ticket_id": ticket_id,
                "source": str(row.get("source") or "dialog"),
                "query": str(row.get("query") or ""),
                "context_ref": dict(row.get("context_ref") or {}),
                "priority": _safe_float(row.get("priority"), 0.5, min_value=0.0, max_value=1.0),
                "budgets": dict(row.get("budgets") or {}),
                "status": str(row.get("status") or "open"),
                "opened_ts": _safe_int(row.get("ts"), _now_ts(), min_value=0),
                "updated_ts": _safe_int(row.get("ts"), _now_ts(), min_value=0),
                "last_event": event,
                "plan": {},
                "enqueue": {},
                "result": {},
                "error": {},
            }
        item["updated_ts"] = _safe_int(row.get("ts"), item.get("updated_ts") or _now_ts(), min_value=0)
        if str(row.get("source") or "").strip():
            item["source"] = _normalize_source(str(row.get("source") or "dialog"))
        if str(row.get("query") or "").strip():
            item["query"] = str(row.get("query") or "")
        if isinstance(row.get("context_ref"), dict) and row.get("context_ref"):
            item["context_ref"] = dict(row.get("context_ref") or {})
        if "priority" in row:
            item["priority"] = _safe_float(row.get("priority"), item.get("priority") or 0.5)
        if isinstance(row.get("budgets"), dict) and row.get("budgets"):
            item["budgets"] = dict(row.get("budgets") or {})
        if isinstance(row.get("plan"), dict) and row.get("plan"):
            item["plan"] = dict(row.get("plan") or {})
        if isinstance(row.get("enqueue"), dict) and row.get("enqueue"):
            item["enqueue"] = dict(row.get("enqueue") or {})
        if isinstance(row.get("result"), dict) and row.get("result"):
            item["result"] = dict(row.get("result") or {})
        if isinstance(row.get("error"), dict) and row.get("error"):
            item["error"] = dict(row.get("error") or {})
        item["last_event"] = event

        status = str(row.get("status") or "").strip().lower()
        if not status:
            if event == "open":
                status = "open"
            elif event == "plan":
                status = "planned"
            elif event == "enqueue":
                status = "enqueued"
            elif event in {"resolve", "negative"}:
                status = "resolved"
            elif event == "fail":
                status = "failed"
            elif event == "stale":
                status = "stale"
            else:
                status = str(item.get("status") or "open")
        item["status"] = status
        tickets[ticket_id] = item

    items = list(tickets.values())
    items.sort(key=lambda x: (_safe_float(x.get("priority"), 0.0), -_safe_int(x.get("opened_ts"), 0)), reverse=True)
    by_status: Dict[str, int] = {}
    for row in items:
        st = str(row.get("status") or "open")
        by_status[st] = int(by_status.get(st, 0)) + 1
    return {
        "ok": True,
        "events_total": len(rows),
        "tickets_total": len(items),
        "tickets_open": int(by_status.get("open", 0) + by_status.get("stale", 0)),
        "by_event": by_event,
        "by_status": by_status,
        "tickets": items,
        "tickets_by_id": {str(x.get("ticket_id") or ""): x for x in items},
    }


def _rebuild_state(last_error: str = "") -> Dict[str, Any]:
    folded = fold_tickets()
    st = _default_state()
    st["updated_ts"] = _now_ts()
    st["last_ticket_ts"] = _safe_int(st.get("last_ticket_ts"), 0, min_value=0)
    rows = ticket_events()
    metrics = _derive_event_metrics(rows)
    if rows:
        st["last_ticket_ts"] = _safe_int(rows[-1].get("ts"), 0, min_value=0)
        st["last_ticket_id"] = str(rows[-1].get("ticket_id") or "")
    st["events_total"] = _safe_int(folded.get("events_total"), 0, min_value=0)
    st["tickets_total"] = _safe_int(folded.get("tickets_total"), 0, min_value=0)
    st["tickets_open"] = _safe_int(folded.get("tickets_open"), 0, min_value=0)
    st["tickets_stale"] = _safe_int((folded.get("by_status") or {}).get("stale"), 0, min_value=0)
    st["tickets_resolved_24h"] = _safe_int(metrics.get("tickets_resolved_24h"), 0, min_value=0)
    st["last_enqueue_ts"] = _safe_int(metrics.get("last_enqueue_ts"), 0, min_value=0)
    st["last_resolve_ts"] = _safe_int(metrics.get("last_resolve_ts"), 0, min_value=0)
    st["by_event"] = dict(folded.get("by_event") or {})
    st["by_status"] = dict(folded.get("by_status") or {})
    st["last_error"] = str(last_error or "")
    _save_state(st)
    return st


def _derive_event_metrics(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    now = _now_ts()
    resolved_24h = 0
    last_enqueue_ts = 0
    last_resolve_ts = 0
    for row in list(rows or []):
        ev = str(row.get("event") or "").strip().lower()
        ts = _safe_int(row.get("ts"), 0, min_value=0)
        if ev == "enqueue" and ts >= last_enqueue_ts:
            last_enqueue_ts = ts
        if ev in {"resolve", "negative"}:
            if ts >= last_resolve_ts:
                last_resolve_ts = ts
            if ts > 0 and (now - ts) <= 86400:
                resolved_24h += 1
    return {
        "tickets_resolved_24h": max(0, int(resolved_24h)),
        "last_enqueue_ts": max(0, int(last_enqueue_ts)),
        "last_resolve_ts": max(0, int(last_resolve_ts)),
    }


def append_ticket_event(
    *,
    event: str,
    ticket_id: str,
    source: str,
    query: str,
    context_text: str = "",
    priority: float = 0.5,
    budgets: Optional[Dict[str, Any]] = None,
    status: str = "",
    plan: Optional[Dict[str, Any]] = None,
    enqueue: Optional[Dict[str, Any]] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None,
    ts: Optional[int] = None,
) -> Dict[str, Any]:
    ev = str(event or "").strip().lower()
    tid = str(ticket_id or "").strip()
    if ev not in ALLOWED_EVENTS:
        return {"ok": False, "error": "event_invalid"}
    if not tid:
        return {"ok": False, "error": "ticket_id_required"}

    src = _normalize_source(source)
    q = str(query or "").strip()
    if not q:
        return {"ok": False, "error": "query_required"}

    row: Dict[str, Any] = {
        "schema": TICKET_EVENT_SCHEMA,
        "ts": int(ts or _now_ts()),
        "event": ev,
        "ticket_id": tid,
        "source": src,
        "query": q,
        "context_ref": {"kind": "hash", "sha256": _sha256_hex(context_text)},
        "priority": _safe_float(priority, 0.5),
        "budgets": _default_budgets(budgets),
        "status": str(status or ""),
    }
    if not row["status"]:
        if ev == "open":
            row["status"] = "open"
        elif ev == "plan":
            row["status"] = "planned"
        elif ev == "enqueue":
            row["status"] = "enqueued"
        elif ev in {"resolve", "negative"}:
            row["status"] = "resolved"
        elif ev == "fail":
            row["status"] = "failed"
        elif ev == "stale":
            row["status"] = "stale"
        else:
            row["status"] = "open"

    if isinstance(plan, dict) and plan:
        row["plan"] = dict(plan)
    if isinstance(enqueue, dict) and enqueue:
        row["enqueue"] = dict(enqueue)
    if isinstance(result, dict) and result:
        row["result"] = dict(result)
    if isinstance(error, dict) and error:
        row["error"] = dict(error)

    with _LOCK:
        _append_jsonl(tickets_path(), row)
        _rebuild_state(last_error=str((error or {}).get("code") or ""))
    return {"ok": True, "row": row}


def _default_open_thresholds(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    src = dict(raw or {})
    return {
        "memory_miss_max": _safe_float(src.get("memory_miss_max"), 0.2, min_value=0.0, max_value=1.0),
        "dedupe_sec": _safe_int(
            src.get("dedupe_sec", os.getenv("ESTER_CURIOSITY_DEDUPE_SEC", "300")),
            300,
            min_value=0,
        ),
    }


def _priority_for(
    source: str,
    recall_score: Optional[float],
    query: str,
) -> float:
    base = {
        "pending": 0.92,
        "memory_miss": 0.78,
        "low_confidence": 0.74,
        "contradiction": 0.86,
        "dialog": 0.58,
        "user": 0.64,
    }.get(source, 0.58)
    bonus = 0.0
    if recall_score is not None:
        bonus += max(0.0, min(1.0, 1.0 - float(recall_score))) * 0.12
    qlen = len(str(query or "").strip())
    if qlen >= 80:
        bonus += 0.03
    if qlen >= 160:
        bonus += 0.02
    return _safe_float(base + bonus, 0.5)


def _find_recent_duplicate(
    *,
    source: str,
    query: str,
    dedupe_sec: int,
) -> str:
    if dedupe_sec <= 0:
        return ""
    now = _now_ts()
    folded = fold_tickets()
    for row in list(folded.get("tickets") or []):
        if str(row.get("source") or "") != source:
            continue
        if str(row.get("query") or "").strip().lower() != query.strip().lower():
            continue
        status = str(row.get("status") or "")
        if status in {"resolved", "failed"}:
            continue
        updated_ts = _safe_int(row.get("updated_ts"), 0, min_value=0)
        if updated_ts <= 0:
            continue
        if now - updated_ts <= dedupe_sec:
            return str(row.get("ticket_id") or "")
    return ""


def maybe_open_ticket(
    query: str,
    *,
    source: str,
    context_text: str,
    recall_score: Optional[float],
    thresholds: Optional[Dict[str, Any]],
    budgets: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    q = str(query or "").strip()
    if not q:
        return {"opened": False, "ticket_id": "", "reason": "query_required", "priority": 0.0}

    src = _normalize_source(source)
    thr = _default_open_thresholds(thresholds)
    mem_threshold = float(thr.get("memory_miss_max") or 0.2)
    should_open = False
    reason = ""

    if src == "pending":
        should_open = True
        reason = "pending_marker"
    elif src == "memory_miss":
        if (recall_score is None) or (float(recall_score) <= mem_threshold):
            should_open = True
            reason = "memory_below_threshold"
    elif src == "low_confidence":
        should_open = True
        reason = "low_confidence"
    elif (recall_score is not None) and (float(recall_score) <= mem_threshold):
        should_open = True
        reason = "recall_low"

    if not should_open:
        return {"opened": False, "ticket_id": "", "reason": "threshold_not_met", "priority": 0.0}

    dup = _find_recent_duplicate(source=src, query=q, dedupe_sec=int(thr.get("dedupe_sec") or 0))
    if dup:
        return {"opened": False, "ticket_id": dup, "reason": "duplicate_open", "priority": 0.0}

    priority = _priority_for(src, recall_score, q)
    tid = "ticket_" + uuid.uuid4().hex
    rep = append_ticket_event(
        event="open",
        ticket_id=tid,
        source=src,
        query=q,
        context_text=str(context_text or ""),
        priority=priority,
        budgets=_default_budgets(budgets),
        status="open",
    )
    if not bool(rep.get("ok")):
        return {
            "opened": False,
            "ticket_id": "",
            "reason": str(rep.get("error") or "open_failed"),
            "priority": 0.0,
        }
    return {"opened": True, "ticket_id": tid, "reason": reason, "priority": priority}


def runtime_snapshot() -> Dict[str, Any]:
    st = _load_state()
    folded = fold_tickets()
    rows = ticket_events()
    metrics = _derive_event_metrics(rows)
    out = {
        "ok": True,
        "schema": STATE_SCHEMA,
        "state_path": str(state_path()),
        "tickets_path": str(tickets_path()),
        "updated_ts": _safe_int(st.get("updated_ts"), 0, min_value=0),
        "last_ticket_ts": _safe_int(st.get("last_ticket_ts"), 0, min_value=0),
        "last_ticket_id": str(st.get("last_ticket_id") or ""),
        "last_error": str(st.get("last_error") or ""),
        "events_total": _safe_int(folded.get("events_total"), 0, min_value=0),
        "tickets_total": _safe_int(folded.get("tickets_total"), 0, min_value=0),
        "tickets_open": _safe_int(folded.get("tickets_open"), 0, min_value=0),
        "tickets_stale": _safe_int((folded.get("by_status") or {}).get("stale"), 0, min_value=0),
        "tickets_resolved_24h": _safe_int(metrics.get("tickets_resolved_24h"), 0, min_value=0),
        "last_enqueue_ts": _safe_int(metrics.get("last_enqueue_ts"), 0, min_value=0),
        "last_resolve_ts": _safe_int(metrics.get("last_resolve_ts"), 0, min_value=0),
        "by_event": dict(folded.get("by_event") or {}),
        "by_status": dict(folded.get("by_status") or {}),
    }
    return out


__all__ = [
    "TICKET_EVENT_SCHEMA",
    "STATE_SCHEMA",
    "tickets_path",
    "state_path",
    "ticket_events",
    "fold_tickets",
    "append_ticket_event",
    "maybe_open_ticket",
    "runtime_snapshot",
]
