# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from modules.garage import agent_factory
from modules.volition import journal as volition_journal

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
    return _env_int("ESTER_CAP_AUDIT_TTL_SEC", 5, 1)


def _max_agents_scan() -> int:
    return _env_int("ESTER_CAP_AUDIT_MAX_AGENTS_SCAN", 2000, 1)


def _journal_tail_lines() -> int:
    return _env_int("ESTER_CAP_AUDIT_TAIL_LINES", 2000, 1)


def _fail_max() -> int:
    return _env_int("ESTER_CAP_AUDIT_FAIL_MAX", 3, 1)


def _clean_list(raw: Any) -> List[str]:
    out: List[str] = []
    for row in list(raw or []):
        s = str(row or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _clone(obj: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(json.dumps(obj, ensure_ascii=True))
    except Exception:
        return dict(obj)


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


def _scan_agents(slot: str, limit: int) -> Tuple[Dict[str, int], int, bool]:
    rows: List[Dict[str, Any]] = []
    try:
        rep = agent_factory.list_agents()
        rows = [dict(x) for x in list(rep.get("agents") or []) if isinstance(x, dict)]
    except Exception:
        rows = []
    rows.sort(key=lambda x: str(x.get("agent_id") or ""))

    scan_limited = len(rows) > max(0, int(limit))
    rows_scan = rows[: max(0, int(limit))]

    counts = {
        "total": 0,
        "capability_mode": 0,
        "template_legacy": 0,
        "raw_capabilities": 0,
        "pure_legacy": 0,
        "authority_missing": 0,
    }

    for row in rows_scan:
        spec = _read_spec_from_row(row)
        src = spec if spec else row

        template_id = str(src.get("template_id") or row.get("template_id") or "").strip()
        caps = _clean_list(src.get("capabilities_effective") or row.get("capabilities_effective") or [])
        authority_source = str(src.get("authority_source") or row.get("authority_source") or "").strip()

        if template_id and (caps or authority_source == "template.capabilities"):
            counts["capability_mode"] += 1
        elif template_id and (not caps):
            counts["template_legacy"] += 1
        elif (not template_id) and caps:
            counts["raw_capabilities"] += 1
        else:
            counts["pure_legacy"] += 1

        if slot == "B":
            try:
                auth = agent_factory.resolve_allowlist_for_spec(src, slot_override="B")
            except Exception:
                auth = {"ok": False, "error": "authority_resolve_exception", "error_code": "AUTHORITY_INVALID"}
            if not bool(auth.get("ok")):
                counts["authority_missing"] += 1

    counts["total"] = len(rows_scan)
    return counts, len(rows_scan), scan_limited


def _tail_lines(path: Path, limit: int) -> List[str]:
    n = max(1, int(limit))
    if not path.exists():
        raise RuntimeError("journal_unavailable")
    try:
        if path.stat().st_size <= 0:
            return []
    except Exception:
        raise RuntimeError("journal_unavailable")

    try:
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
    except Exception:
        raise RuntimeError("journal_unavailable")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-n:]


def _inc(bucket: Dict[str, int], code: str) -> None:
    key = str(code or "").strip() or "UNKNOWN"
    bucket[key] = int(bucket.get(key) or 0) + 1


def _build_telemetry(rows: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    clamp = {
        "total_recent": 0,
        "last_ts": 0,
        "last_agent_id": "",
        "last_reason_code": "",
        "last_warnings": [],
        "by_code": {},
    }
    deny = {
        "total_recent": 0,
        "last_ts": 0,
        "last_step": "",
        "last_agent_id": "",
        "last_reason_code": "",
        "last_action_id": "",
        "by_code": {},
    }
    recent_pairs: List[Tuple[int, int, Dict[str, Any]]] = []
    seq = 0

    for row in rows:
        seq += 1
        if not isinstance(row, dict):
            continue
        step = str(row.get("step") or "").strip()
        allowed = bool(row.get("allowed"))
        if step not in {"agent.create", "agent.queue.enqueue", "agent.run.step"}:
            continue

        metadata = dict(row.get("metadata") or {})
        reason_code = str(row.get("reason_code") or ("ALLOW" if allowed else "DENY")).strip()
        ts = int(row.get("ts") or 0)
        agent_id = str(row.get("agent_id") or metadata.get("agent_id") or "").strip()
        action_id = str(row.get("action_id") or metadata.get("action_id") or "").strip()
        warnings = _clean_list(metadata.get("warnings") or metadata.get("authority_warnings") or [])

        is_deny = (not allowed)
        is_clamp = bool(step == "agent.create" and allowed and (warnings or ("CLAMP" in reason_code.upper())))

        if not is_deny and not is_clamp:
            continue

        event = {
            "ts": ts,
            "step": step,
            "allowed": bool(allowed),
            "agent_id": agent_id,
            "reason_code": reason_code,
            "action_id": action_id,
            "details": metadata,
        }
        recent_pairs.append((ts, seq, event))

        if is_clamp:
            clamp["total_recent"] = int(clamp.get("total_recent") or 0) + 1
            _inc(clamp["by_code"], reason_code or "ALLOW_CLAMP")
            for warn in warnings:
                _inc(clamp["by_code"], warn)
            if ts >= int(clamp.get("last_ts") or 0):
                clamp["last_ts"] = ts
                clamp["last_agent_id"] = agent_id
                clamp["last_reason_code"] = reason_code
                clamp["last_warnings"] = list(warnings)

        if is_deny:
            deny["total_recent"] = int(deny.get("total_recent") or 0) + 1
            _inc(deny["by_code"], reason_code or "DENY")
            if ts >= int(deny.get("last_ts") or 0):
                deny["last_ts"] = ts
                deny["last_step"] = step
                deny["last_agent_id"] = agent_id
                deny["last_reason_code"] = reason_code
                deny["last_action_id"] = action_id

    recent_pairs.sort(key=lambda x: (int(x[0]), int(x[1])))
    recent = [pair[2] for pair in recent_pairs[-30:]]
    return clamp, deny, recent


def _read_journal_tail(limit: int) -> Tuple[List[Dict[str, Any]], int]:
    try:
        path = volition_journal.journal_path()
    except Exception:
        raise RuntimeError("journal_unavailable")

    lines = _tail_lines(path, limit)
    rows: List[Dict[str, Any]] = []
    for line in lines:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows, len(lines)


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
            _LAST_ROLLBACK_REASON = str(reason or "capability_audit_failure")
        return {
            "fail_streak": int(_FAIL_STREAK),
            "fail_max": int(fail_max),
            "mode_forced": str(_MODE_FORCED or ""),
            "last_rollback_reason": str(_LAST_ROLLBACK_REASON or ""),
        }


def _blank_payload(*, slot: str, ttl: int, fail_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": True,
        "slot": slot,
        "degraded": False,
        "error": "",
        "agents": {
            "total": 0,
            "capability_mode": 0,
            "template_legacy": 0,
            "raw_capabilities": 0,
            "pure_legacy": 0,
            "authority_missing": 0,
        },
        "clamp": {
            "total_recent": 0,
            "last_ts": 0,
            "last_agent_id": "",
            "last_reason_code": "",
            "last_warnings": [],
            "by_code": {},
        },
        "deny": {
            "total_recent": 0,
            "last_ts": 0,
            "last_step": "",
            "last_agent_id": "",
            "last_reason_code": "",
            "last_action_id": "",
            "by_code": {},
        },
        "recent_events": [],
        "perf": {
            "cache_ttl_sec": int(ttl),
            "scanned_agents": 0,
            "journal_tail_lines": 0,
            "build_ms": 0,
            "fail_streak": int(fail_state.get("fail_streak") or 0),
            "fail_max": int(fail_state.get("fail_max") or _fail_max()),
            "audit_mode_forced": str(fail_state.get("mode_forced") or ""),
            "audit_last_rollback_reason": str(fail_state.get("last_rollback_reason") or ""),
        },
        "audit_mode_forced": str(fail_state.get("mode_forced") or ""),
        "audit_last_rollback_reason": str(fail_state.get("last_rollback_reason") or ""),
    }


def _build_uncached(cache_ttl: int, max_scan: int, tail_lines: int, fail_max: int) -> Dict[str, Any]:
    raw_slot = _slot()
    fail_state = _failure_snapshot(fail_max)
    slot = "A" if str(fail_state.get("mode_forced") or "") == "A" else raw_slot

    started = time.perf_counter()
    payload = _blank_payload(slot=slot, ttl=cache_ttl, fail_state=fail_state)
    payload["degraded"] = bool(slot != raw_slot)

    try:
        counts, scanned, scan_limited = _scan_agents(slot, max_scan)
        payload["agents"] = counts
        payload["perf"]["scanned_agents"] = int(scanned)
        if scan_limited:
            payload["degraded"] = True
            payload["error"] = "agents_scan_limited"

        if slot == "B":
            rows, read_lines = _read_journal_tail(tail_lines)
            clamp, deny, recent = _build_telemetry(rows)
            payload["clamp"] = clamp
            payload["deny"] = deny
            payload["recent_events"] = recent
            payload["perf"]["journal_tail_lines"] = int(read_lines)
            _note_success()
        else:
            payload["agents"]["authority_missing"] = 0
    except Exception as exc:
        err = str(exc or "audit_build_failed").strip() or "audit_build_failed"
        if err not in {"journal_unavailable"}:
            err = "audit_build_failed"
        payload["ok"] = False
        payload["degraded"] = True
        payload["error"] = err

        if slot == "B":
            fail_state = _note_failure(err, fail_max)
            forced_slot = "A" if str(fail_state.get("mode_forced") or "") == "A" else slot
            payload["slot"] = forced_slot
            if forced_slot == "A":
                counts, scanned, scan_limited = _scan_agents("A", max_scan)
                payload["agents"] = counts
                payload["agents"]["authority_missing"] = 0
                payload["perf"]["scanned_agents"] = int(scanned)
                if scan_limited:
                    payload["degraded"] = True
            payload["audit_mode_forced"] = str(fail_state.get("mode_forced") or "")
            payload["audit_last_rollback_reason"] = str(fail_state.get("last_rollback_reason") or "")

    elapsed_ms = int((time.perf_counter() - started) * 1000.0)
    fail_state = _failure_snapshot(fail_max)
    payload["perf"]["build_ms"] = max(0, elapsed_ms)
    payload["perf"]["fail_streak"] = int(fail_state.get("fail_streak") or 0)
    payload["perf"]["fail_max"] = int(fail_state.get("fail_max") or fail_max)
    payload["perf"]["audit_mode_forced"] = str(fail_state.get("mode_forced") or "")
    payload["perf"]["audit_last_rollback_reason"] = str(fail_state.get("last_rollback_reason") or "")
    payload["audit_mode_forced"] = str(fail_state.get("mode_forced") or "")
    payload["audit_last_rollback_reason"] = str(fail_state.get("last_rollback_reason") or "")
    return payload


def build_capability_audit() -> Dict[str, Any]:
    global _CACHE_PAYLOAD, _CACHE_KEY, _CACHE_TS_MONO

    ttl = _cache_ttl_sec()
    max_scan = _max_agents_scan()
    tail_lines = _journal_tail_lines()
    fail_max = _fail_max()
    slot = _slot()
    fail_state = _failure_snapshot(fail_max)
    slot_effective = "A" if str(fail_state.get("mode_forced") or "") == "A" else slot
    cache_key = f"{slot_effective}|{max_scan}|{tail_lines}|{fail_max}"
    now_mono = time.monotonic()

    with _LOCK:
        if (
            _CACHE_PAYLOAD is not None
            and _CACHE_KEY == cache_key
            and (now_mono - _CACHE_TS_MONO) <= float(ttl)
        ):
            return _clone(dict(_CACHE_PAYLOAD))

    payload = _build_uncached(ttl, max_scan, tail_lines, fail_max)
    with _LOCK:
        _CACHE_PAYLOAD = _clone(payload)
        _CACHE_KEY = cache_key
        _CACHE_TS_MONO = now_mono
    return _clone(payload)


__all__ = ["build_capability_audit"]
