# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from modules.garage import agent_factory

_LOCK = threading.RLock()

_CACHE_PAYLOAD: Dict[str, Any] | None = None
_CACHE_KEY = ""
_CACHE_TS_MONO = 0.0

_FAIL_STREAK = 0
_MODE_FORCED = ""
_LAST_ROLLBACK_REASON = ""


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    try:
        return max(min_value, int(os.getenv(name, str(default)) or default))
    except Exception:
        return max(min_value, int(default))


def _cache_ttl_sec() -> int:
    return _env_int("ESTER_DRIFT_TTL_SEC", 5, 1)


def _fail_max() -> int:
    return _env_int("ESTER_DRIFT_FAIL_MAX", 3, 1)


def _max_agents_scan() -> int:
    return _env_int("ESTER_DRIFT_MAX_AGENTS_SCAN", 2000, 1)


def _max_last_seen() -> int:
    return _env_int("ESTER_DRIFT_MAX_LAST_SEEN", 5000, 1)


def _events_tail_lines_default() -> int:
    return _env_int("ESTER_DRIFT_EVENTS_TAIL_LINES", 200, 1)


def _persist_dir() -> Path:
    root = str(os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    return Path(root).resolve()


def _drift_root() -> Path:
    return (_persist_dir() / "capability_drift").resolve()


def _events_path() -> Path:
    return (_drift_root() / "events.jsonl").resolve()


def _last_seen_path() -> Path:
    return (_drift_root() / "last_seen.json").resolve()


def _clean_list(raw: Any) -> List[str]:
    out: List[str] = []
    for row in list(raw or []):
        s = str(row or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def normalize_allowlist(raw: Any) -> List[str]:
    return sorted(_clean_list(raw))


def allowlist_hash(raw: Any) -> str:
    norm = normalize_allowlist(raw)
    blob = json.dumps(norm, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _clone(obj: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(json.dumps(obj, ensure_ascii=True))
    except Exception:
        return dict(obj)


def _failure_snapshot(fail_max: int) -> Dict[str, Any]:
    with _LOCK:
        return {
            "fail_streak": int(_FAIL_STREAK),
            "fail_max": int(fail_max),
            "mode_forced": str(_MODE_FORCED or ""),
            "last_rollback_reason": str(_LAST_ROLLBACK_REASON or ""),
        }


def _note_success() -> None:
    global _FAIL_STREAK
    with _LOCK:
        if not _MODE_FORCED:
            _FAIL_STREAK = 0


def _note_failure(reason: str, fail_max: int) -> Dict[str, Any]:
    global _FAIL_STREAK, _MODE_FORCED, _LAST_ROLLBACK_REASON
    with _LOCK:
        _FAIL_STREAK = int(_FAIL_STREAK) + 1
        if _FAIL_STREAK >= int(fail_max):
            _MODE_FORCED = "A"
            _LAST_ROLLBACK_REASON = str(reason or "capability_drift_failure")
        return {
            "fail_streak": int(_FAIL_STREAK),
            "fail_max": int(fail_max),
            "mode_forced": str(_MODE_FORCED or ""),
            "last_rollback_reason": str(_LAST_ROLLBACK_REASON or ""),
        }


def _tail_lines(path: Path, limit: int) -> List[str]:
    n = max(1, int(limit))
    if (not path.exists()) or (path.stat().st_size <= 0):
        return []
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        block = 4096
        data = b""
        found = 0
        while pos > 0 and found <= n:
            step = min(block, pos)
            pos -= step
            f.seek(pos, os.SEEK_SET)
            chunk = f.read(step)
            data = chunk + data
            found = data.count(b"\n")
        text = data.decode("utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-n:]


def _read_spec_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    spec_path = str(row.get("spec_path") or "").strip()
    if not spec_path:
        return {}
    p = Path(spec_path)
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        return {}
    return {}


def _load_last_seen() -> Dict[str, Dict[str, Any]]:
    path = _last_seen_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"last_seen_parse_error:{exc.__class__.__name__}")
    if not isinstance(raw, dict):
        raise RuntimeError("last_seen_invalid")
    out: Dict[str, Dict[str, Any]] = {}
    for agent_id, row in raw.items():
        aid = str(agent_id or "").strip()
        if not aid or (not isinstance(row, dict)):
            continue
        out[aid] = dict(row)
    return out


def _compact_last_seen(
    src: Dict[str, Dict[str, Any]],
    max_items: int,
) -> Dict[str, Dict[str, Any]]:
    if len(src) <= int(max_items):
        return src
    rows = sorted(
        ((aid, dict(row or {})) for aid, row in src.items()),
        key=lambda pair: int((pair[1] or {}).get("ts") or 0),
        reverse=True,
    )
    out: Dict[str, Dict[str, Any]] = {}
    for aid, row in rows[: int(max_items)]:
        out[aid] = row
    return out


def _save_last_seen(src: Dict[str, Dict[str, Any]], max_items: int) -> int:
    root = _drift_root()
    root.mkdir(parents=True, exist_ok=True)
    compacted = _compact_last_seen(dict(src), max_items)
    payload = json.dumps(compacted, ensure_ascii=True, indent=2)
    path = _last_seen_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)
    return len(compacted)


def _append_event(row: Dict[str, Any]) -> None:
    root = _drift_root()
    root.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row or {}), ensure_ascii=True, separators=(",", ":"))
    with _events_path().open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _read_events_tail(limit_events: int, tail_lines: int) -> Tuple[List[Dict[str, Any]], int]:
    path = _events_path()
    lines = _tail_lines(path, tail_lines)
    out: List[Dict[str, Any]] = []
    for line in lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    out.sort(key=lambda x: int(x.get("ts") or 0))
    return out[-max(1, int(limit_events)) :], len(lines)


def _diff_lists(old_list: List[str], new_list: List[str]) -> Tuple[List[str], List[str]]:
    old_set = set(normalize_allowlist(old_list))
    new_set = set(normalize_allowlist(new_list))
    added = sorted(new_set - old_set)[:10]
    removed = sorted(old_set - new_set)[:10]
    return added, removed


def _classify_change(
    old_list: List[str],
    new_list: List[str],
    old_hash: str,
    new_hash: str,
) -> Tuple[str, str, List[str], List[str]]:
    added, removed = _diff_lists(old_list, new_list)
    if added:
        return "HIGH", "ESCALATION", added, removed
    if removed:
        return "LOW", "SHRINK", added, removed
    if str(old_hash or "") != str(new_hash or ""):
        return "MEDIUM", "MUTATION", added, removed
    return "LOW", "UNKNOWN", added, removed


def _make_event(
    *,
    ts: int,
    agent_id: str,
    kind: str,
    severity: str,
    template_id: str,
    caps_hash: str,
    old_hash: str,
    new_hash: str,
    stored_hash: str,
    computed_hash: str,
    added: List[str],
    removed: List[str],
    reason_code: str,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "ts": int(ts),
        "agent_id": str(agent_id or ""),
        "kind": str(kind or "UNKNOWN"),
        "severity": str(severity or "LOW"),
        "template_id": str(template_id or ""),
        "caps_hash": str(caps_hash or ""),
        "old_hash": str(old_hash or ""),
        "new_hash": str(new_hash or ""),
        "stored_hash": str(stored_hash or ""),
        "computed_hash": str(computed_hash or ""),
        "added": [str(x) for x in list(added or [])[:10] if str(x).strip()],
        "removed": [str(x) for x in list(removed or [])[:10] if str(x).strip()],
        "reason_code": str(reason_code or "UNKNOWN"),
        "details": dict(details or {}),
    }


def _build_last_event(src: Dict[str, Any] | None) -> Dict[str, Any]:
    row = dict(src or {})
    return {
        "ts": int(row.get("ts") or 0),
        "agent_id": str(row.get("agent_id") or ""),
        "kind": str(row.get("kind") or ""),
        "severity": str(row.get("severity") or ""),
        "reason_code": str(row.get("reason_code") or ""),
        "old_hash": str(row.get("old_hash") or ""),
        "new_hash": str(row.get("new_hash") or ""),
        "template_id": str(row.get("template_id") or ""),
        "added": [str(x) for x in list(row.get("added") or []) if str(x).strip()],
        "removed": [str(x) for x in list(row.get("removed") or []) if str(x).strip()],
    }


def scan_agents_for_drift(*, write: bool, max_agents: int) -> Dict[str, Any]:
    slot = _slot()
    do_write = bool(slot == "B" and bool(write))
    max_scan = max(1, int(max_agents or _max_agents_scan()))
    tail_lines = _events_tail_lines_default()
    now_ts = int(time.time())

    rep = agent_factory.list_agents()
    rows = [dict(x) for x in list(rep.get("agents") or []) if isinstance(x, dict)]
    rows.sort(key=lambda x: str(x.get("agent_id") or ""))

    scan_limited = len(rows) > max_scan
    rows_scan = rows[:max_scan]

    last_seen: Dict[str, Dict[str, Any]] = {}
    if slot == "B":
        last_seen = _load_last_seen()

    mismatches = 0
    changed = 0
    caps_changed = 0
    escalations = 0
    events_written = 0
    emitted_events: List[Dict[str, Any]] = []

    for row in rows_scan:
        spec = _read_spec_from_row(row)
        src = spec if spec else row

        agent_id = str(src.get("agent_id") or row.get("agent_id") or "").strip()
        if not agent_id:
            continue
        template_id = str(src.get("template_id") or row.get("template_id") or "").strip()
        caps_effective = normalize_allowlist(src.get("capabilities_effective") or row.get("capabilities_effective") or [])
        caps_hash = allowlist_hash(caps_effective) if caps_effective else ""

        stored_allowlist = normalize_allowlist(src.get("allowed_actions") or row.get("allowed_actions") or [])
        stored_hash = str(src.get("allowed_actions_hash") or "").strip() or allowlist_hash(stored_allowlist)

        computed_allowlist: List[str] = []
        computed_hash = ""
        try:
            allow_rep = agent_factory.resolve_allowlist_for_spec(src, slot_override="B")
        except Exception:
            allow_rep = {"ok": False, "error": "authority_resolve_exception", "error_code": "AUTHORITY_INVALID"}

        computed_ok = bool(allow_rep.get("ok"))
        if computed_ok:
            computed_allowlist = normalize_allowlist(allow_rep.get("allowed_actions") or [])
            computed_hash = allowlist_hash(computed_allowlist)

        prev = dict(last_seen.get(agent_id) or {})
        prev_hash = str(prev.get("allowlist_hash") or "").strip()
        prev_caps_hash = str(prev.get("caps_hash") or "").strip()
        prev_allowlist = normalize_allowlist(prev.get("allowlist") or [])

        if computed_ok and computed_hash != stored_hash:
            mismatches += 1
            added, removed = _diff_lists(computed_allowlist, stored_allowlist)
            reason_code = "TAMPER_SUSPECT" if added else ("SHRINK" if removed else "MUTATION")
            severity = "HIGH" if added else ("LOW" if removed else "MEDIUM")
            event = _make_event(
                ts=now_ts,
                agent_id=agent_id,
                kind="SPEC_MISMATCH",
                severity=severity,
                template_id=template_id,
                caps_hash=caps_hash,
                old_hash=computed_hash,
                new_hash=stored_hash,
                stored_hash=stored_hash,
                computed_hash=computed_hash,
                added=added,
                removed=removed,
                reason_code=reason_code,
                details={
                    "slot": slot,
                    "source": "computed_vs_stored",
                    "stored_len": len(stored_allowlist),
                    "computed_len": len(computed_allowlist),
                },
            )
            emitted_events.append(event)

        if slot == "B" and computed_ok and prev_hash and prev_hash != computed_hash:
            changed += 1
            severity, reason_code, added, removed = _classify_change(
                prev_allowlist,
                computed_allowlist,
                prev_hash,
                computed_hash,
            )
            if added:
                escalations += 1
            event = _make_event(
                ts=now_ts,
                agent_id=agent_id,
                kind="ALLOWLIST_CHANGED",
                severity=severity,
                template_id=template_id,
                caps_hash=caps_hash,
                old_hash=prev_hash,
                new_hash=computed_hash,
                stored_hash=stored_hash,
                computed_hash=computed_hash,
                added=added,
                removed=removed,
                reason_code=reason_code,
                details={"slot": slot, "source": "last_seen_vs_current"},
            )
            emitted_events.append(event)

        if slot == "B" and prev_caps_hash and caps_hash and prev_caps_hash != caps_hash:
            caps_changed += 1
            event = _make_event(
                ts=now_ts,
                agent_id=agent_id,
                kind="CAPS_CHANGED",
                severity="MEDIUM",
                template_id=template_id,
                caps_hash=caps_hash,
                old_hash=prev_caps_hash,
                new_hash=caps_hash,
                stored_hash=stored_hash,
                computed_hash=computed_hash,
                added=[],
                removed=[],
                reason_code="UNKNOWN",
                details={"slot": slot, "source": "caps_hash_changed"},
            )
            emitted_events.append(event)

        if do_write and computed_ok:
            last_seen[agent_id] = {
                "ts": int(now_ts),
                "allowlist_hash": str(computed_hash or ""),
                "allowlist_len": int(len(computed_allowlist)),
                "template_id": str(template_id or ""),
                "caps_hash": str(caps_hash or ""),
                "allowlist": list(computed_allowlist),
            }

    if do_write:
        for event in emitted_events:
            _append_event(event)
            events_written += 1
        last_seen_size = _save_last_seen(last_seen, _max_last_seen())
    elif slot == "B":
        last_seen_size = len(last_seen)
    else:
        last_seen_size = 0

    if slot == "B":
        recent_events, events_tail_lines = _read_events_tail(10, tail_lines)
    else:
        recent_events, events_tail_lines = [], 0

    last_event = _build_last_event(recent_events[-1] if recent_events else None)
    last_event_ts = int(last_event.get("ts") or 0)

    return {
        "ok": True,
        "slot": slot,
        "write": bool(do_write),
        "scanned_agents": len(rows_scan),
        "total_agents": len(rows),
        "scan_limited": bool(scan_limited),
        "mismatches": int(mismatches),
        "changed": int(changed),
        "caps_changed": int(caps_changed),
        "escalations": int(escalations),
        "last_event_ts": int(last_event_ts),
        "last_event": last_event,
        "recent_events": recent_events,
        "events_written": int(events_written),
        "events_tail_lines": int(events_tail_lines),
        "last_seen_size": int(last_seen_size),
    }


def _blank_payload(slot: str, ttl: int, fail_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": True,
        "slot": slot,
        "degraded": False,
        "error": "",
        "summary": {
            "scanned_agents": 0,
            "scan_limited": False,
            "mismatches": 0,
            "changed": 0,
            "caps_changed": 0,
            "escalations": 0,
            "last_event_ts": 0,
        },
        "last_event": {
            "ts": 0,
            "agent_id": "",
            "kind": "",
            "severity": "",
            "reason_code": "",
            "old_hash": "",
            "new_hash": "",
            "template_id": "",
            "added": [],
            "removed": [],
        },
        "recent_events": [],
        "perf": {
            "cache_ttl_sec": int(ttl),
            "build_ms": 0,
            "last_seen_size": 0,
            "events_tail_lines": 0,
            "fail_streak": int(fail_state.get("fail_streak") or 0),
            "fail_max": int(fail_state.get("fail_max") or _fail_max()),
            "mode_forced": str(fail_state.get("mode_forced") or ""),
            "last_rollback_reason": str(fail_state.get("last_rollback_reason") or ""),
        },
    }


def _build_from_scan(scan: Dict[str, Any], ttl: int, fail_state: Dict[str, Any], degraded: bool) -> Dict[str, Any]:
    return {
        "ok": bool(scan.get("ok")),
        "slot": str(scan.get("slot") or "A"),
        "degraded": bool(degraded or bool(scan.get("scan_limited"))),
        "error": "",
        "summary": {
            "scanned_agents": int(scan.get("scanned_agents") or 0),
            "scan_limited": bool(scan.get("scan_limited")),
            "mismatches": int(scan.get("mismatches") or 0),
            "changed": int(scan.get("changed") or 0),
            "caps_changed": int(scan.get("caps_changed") or 0),
            "escalations": int(scan.get("escalations") or 0),
            "last_event_ts": int(scan.get("last_event_ts") or 0),
        },
        "last_event": _build_last_event(dict(scan.get("last_event") or {})),
        "recent_events": [dict(x) for x in list(scan.get("recent_events") or []) if isinstance(x, dict)][-10:],
        "perf": {
            "cache_ttl_sec": int(ttl),
            "build_ms": 0,
            "last_seen_size": int(scan.get("last_seen_size") or 0),
            "events_tail_lines": int(scan.get("events_tail_lines") or 0),
            "fail_streak": int(fail_state.get("fail_streak") or 0),
            "fail_max": int(fail_state.get("fail_max") or _fail_max()),
            "mode_forced": str(fail_state.get("mode_forced") or ""),
            "last_rollback_reason": str(fail_state.get("last_rollback_reason") or ""),
        },
    }


def build_capability_drift() -> Dict[str, Any]:
    global _CACHE_PAYLOAD, _CACHE_KEY, _CACHE_TS_MONO

    ttl = _cache_ttl_sec()
    max_scan = _max_agents_scan()
    fail_max = _fail_max()
    raw_slot = _slot()
    fail_state = _failure_snapshot(fail_max)
    slot_effective = "A" if str(fail_state.get("mode_forced") or "") == "A" else raw_slot
    cache_key = f"{slot_effective}|{max_scan}|{fail_max}"
    now_mono = time.monotonic()

    with _LOCK:
        if (
            _CACHE_PAYLOAD is not None
            and _CACHE_KEY == cache_key
            and (now_mono - _CACHE_TS_MONO) <= float(ttl)
        ):
            return _clone(dict(_CACHE_PAYLOAD))

    started = time.perf_counter()
    payload = _blank_payload(slot_effective, ttl, fail_state)
    payload["degraded"] = bool(slot_effective != raw_slot)

    try:
        scan = scan_agents_for_drift(write=(slot_effective == "B"), max_agents=max_scan)
        if slot_effective == "B":
            _note_success()
        fail_state = _failure_snapshot(fail_max)
        payload = _build_from_scan(scan, ttl, fail_state, bool(slot_effective != raw_slot))
    except Exception as exc:
        err = str(exc or "drift_build_failed").strip() or "drift_build_failed"
        payload["ok"] = False
        payload["degraded"] = True
        payload["error"] = err
        if slot_effective == "B":
            fail_state = _note_failure(err, fail_max)
            forced_slot = "A" if str(fail_state.get("mode_forced") or "") == "A" else "B"
            payload["slot"] = forced_slot
            payload["perf"]["mode_forced"] = str(fail_state.get("mode_forced") or "")
            payload["perf"]["last_rollback_reason"] = str(fail_state.get("last_rollback_reason") or "")
            if forced_slot == "A":
                scan = scan_agents_for_drift(write=False, max_agents=max_scan)
                payload = _build_from_scan(scan, ttl, fail_state, True)
                payload["ok"] = False
                payload["degraded"] = True
                payload["error"] = err
                payload["slot"] = "A"

    elapsed_ms = int((time.perf_counter() - started) * 1000.0)
    fail_state = _failure_snapshot(fail_max)
    payload["perf"]["build_ms"] = max(0, elapsed_ms)
    payload["perf"]["fail_streak"] = int(fail_state.get("fail_streak") or 0)
    payload["perf"]["fail_max"] = int(fail_state.get("fail_max") or fail_max)
    payload["perf"]["mode_forced"] = str(fail_state.get("mode_forced") or "")
    payload["perf"]["last_rollback_reason"] = str(fail_state.get("last_rollback_reason") or "")

    with _LOCK:
        _CACHE_PAYLOAD = _clone(payload)
        _CACHE_KEY = cache_key
        _CACHE_TS_MONO = now_mono
    return _clone(payload)


__all__ = [
    "normalize_allowlist",
    "allowlist_hash",
    "scan_agents_for_drift",
    "build_capability_drift",
]

