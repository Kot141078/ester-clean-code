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
try:
    from modules.runtime import evidence_signing
except Exception:  # pragma: no cover
    evidence_signing = None  # type: ignore
try:
    from modules.runtime import l4w_witness
except Exception:  # pragma: no cover
    l4w_witness = None  # type: ignore

_LOCK = threading.RLock()

_STATE_CACHE: Dict[str, Dict[str, Any]] | None = None
_STATE_CACHE_TS_MONO = 0.0

_STATUS_CACHE: Dict[str, Any] | None = None
_STATUS_CACHE_KEY = ""
_STATUS_CACHE_TS_MONO = 0.0

_FAIL_STREAK = 0
_MODE_FORCED = ""
_LAST_ROLLBACK_REASON = ""
_BOOL_TRUE = {"1", "true", "yes", "on", "y"}


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    try:
        return max(min_value, int(os.getenv(name, str(default)) or default))
    except Exception:
        return max(min_value, int(default))


def _env_bool(name: str, default: bool) -> bool:
    raw_default = "1" if bool(default) else "0"
    raw = str(os.getenv(name, raw_default) or raw_default).strip().lower()
    return raw in _BOOL_TRUE


def _ttl_sec() -> int:
    return _env_int("ESTER_QUARANTINE_TTL_SEC", 5, 1)


def _fail_max() -> int:
    return _env_int("ESTER_QUARANTINE_FAIL_MAX", 3, 1)


def _max_state_items() -> int:
    return _env_int("ESTER_QUARANTINE_MAX_STATE", 5000, 1)


def _tail_lines_default() -> int:
    return _env_int("ESTER_QUARANTINE_TAIL_LINES", 200, 1)


def _max_agents_scan_default() -> int:
    return _env_int("ESTER_DRIFT_MAX_AGENTS_SCAN", 2000, 1)


def _challenge_sec() -> int:
    raw = str(os.getenv("ESTER_QUARANTINE_CHALLENGE_SEC", "3600") or "3600").strip()
    try:
        val = int(raw)
    except Exception:
        val = 3600
    if val <= 0:
        val = 3600
    return max(60, val)


def _evidence_sig_required(slot: str) -> bool:
    raw = str(os.getenv("ESTER_EVIDENCE_SIG_REQUIRED", "") or "").strip()
    if raw:
        return _env_bool("ESTER_EVIDENCE_SIG_REQUIRED", bool(slot == "B"))
    return bool(slot == "B")


def _l4w_required(slot: str) -> bool:
    raw = str(os.getenv("ESTER_L4W_REQUIRED", "") or "").strip()
    if raw:
        return _env_bool("ESTER_L4W_REQUIRED", bool(slot == "B"))
    return bool(slot == "B")


def _l4w_chain_enforced(slot: str) -> bool:
    if _env_bool("ESTER_L4W_CHAIN_DISABLED", False):
        return False
    raw = str(os.getenv("ESTER_L4W_CHAIN_REQUIRED", "") or "").strip()
    if raw:
        return _env_bool("ESTER_L4W_CHAIN_REQUIRED", bool(slot == "B"))
    return bool(slot == "B")


def _expire_tail_lines() -> int:
    return _env_int("ESTER_QUARANTINE_EXPIRE_TAIL_LINES", 200, 1)


def _persist_dir() -> Path:
    root = str(os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    return Path(root).resolve()


def _drift_root() -> Path:
    return (_persist_dir() / "capability_drift").resolve()


def _state_path() -> Path:
    return (_drift_root() / "quarantine_state.json").resolve()


def _events_path() -> Path:
    return (_drift_root() / "quarantine_events.jsonl").resolve()


def _last_seen_path() -> Path:
    return (_drift_root() / "last_seen.json").resolve()


def _evidence_root() -> Path:
    return (_drift_root() / "evidence").resolve()


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _resolve_evidence_path(evidence_path: str) -> Dict[str, Any]:
    raw = str(evidence_path or "").strip()
    if not raw:
        return {"ok": False, "error_code": "EVIDENCE_PATH_REQUIRED", "error": "evidence_path_required"}
    root = _evidence_root()
    root.mkdir(parents=True, exist_ok=True)
    p = Path(raw)
    resolved = p.resolve() if p.is_absolute() else (root / p).resolve()
    if not _path_within(resolved, root):
        return {
            "ok": False,
            "error_code": "EVIDENCE_PATH_FORBIDDEN",
            "error": "evidence_path_forbidden",
            "evidence_root": str(root),
            "evidence_path": str(resolved),
        }
    return {
        "ok": True,
        "evidence_root": str(root),
        "evidence_path": str(resolved),
        "evidence_rel_path": str(resolved.relative_to(root)).replace("\\", "/"),
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(131072)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _clean_list(raw: Any) -> List[str]:
    out: List[str] = []
    for row in list(raw or []):
        s = str(row or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def normalize_allowlist(raw: Any) -> List[str]:
    return sorted(_clean_list(raw))


def _list_hash(raw: Any) -> str:
    norm = normalize_allowlist(raw)
    blob = json.dumps(norm, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _event_id(agent_id: str, kind: str, reason_code: str, computed_hash: str, stored_hash: str) -> str:
    src = "|".join(
        [
            str(agent_id or ""),
            str(kind or ""),
            str(reason_code or ""),
            str(computed_hash or ""),
            str(stored_hash or ""),
        ]
    ).encode("utf-8")
    return hashlib.sha256(src).hexdigest()


def _clone(obj: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(json.dumps(obj, ensure_ascii=True))
    except Exception:
        return dict(obj)


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


def _failure_snapshot(fail_max: int) -> Dict[str, Any]:
    with _LOCK:
        return {
            "fail_streak": int(_FAIL_STREAK),
            "fail_max": int(fail_max),
            "mode_forced": str(_MODE_FORCED or ""),
            "last_rollback_reason": str(_LAST_ROLLBACK_REASON or ""),
        }


def _effective_slot() -> str:
    raw = _slot()
    with _LOCK:
        forced = str(_MODE_FORCED or "")
    if forced == "A":
        return "A"
    return raw


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
            _LAST_ROLLBACK_REASON = str(reason or "quarantine_failure")
        return {
            "fail_streak": int(_FAIL_STREAK),
            "fail_max": int(fail_max),
            "mode_forced": str(_MODE_FORCED or ""),
            "last_rollback_reason": str(_LAST_ROLLBACK_REASON or ""),
        }


def _load_last_seen() -> Dict[str, Dict[str, Any]]:
    p = _last_seen_path()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for aid, row in raw.items():
        key = str(aid or "").strip()
        if not key or (not isinstance(row, dict)):
            continue
        out[key] = dict(row)
    return out


def _normalize_state_entry(agent_id: str, row: Dict[str, Any]) -> Dict[str, Any]:
    out = _state_row_defaults(agent_id)
    src = dict(row or {})
    out.update(src)
    out["agent_id"] = str(out.get("agent_id") or agent_id or "")
    out["active"] = bool(out.get("active"))
    out["since_ts"] = max(0, int(out.get("since_ts") or 0))
    out["event_id"] = str(out.get("event_id") or "")
    out["kind"] = str(out.get("kind") or "")
    out["severity"] = str(out.get("severity") or "")
    out["reason_code"] = str(out.get("reason_code") or "")
    out["template_id"] = str(out.get("template_id") or "")
    out["caps_hash"] = str(out.get("caps_hash") or "")
    out["computed_hash"] = str(out.get("computed_hash") or "")
    out["stored_hash"] = str(out.get("stored_hash") or "")
    out["added"] = [str(x) for x in list(out.get("added") or [])[:10] if str(x).strip()]
    out["removed"] = [str(x) for x in list(out.get("removed") or [])[:10] if str(x).strip()]
    out["last_seen_ts"] = max(0, int(out.get("last_seen_ts") or 0))
    out["challenge_open_ts"] = max(0, int(out.get("challenge_open_ts") or 0))
    out["challenge_sec"] = max(60, int(out.get("challenge_sec") or _challenge_sec()))
    out["challenge_deadline_ts"] = max(0, int(out.get("challenge_deadline_ts") or 0))
    if out["active"] and out["challenge_open_ts"] <= 0:
        out["challenge_open_ts"] = int(out["since_ts"] or int(time.time()))
    if out["active"] and out["challenge_deadline_ts"] <= 0:
        out["challenge_deadline_ts"] = int(out["challenge_open_ts"] or int(time.time())) + int(out["challenge_sec"])
    out["expired"] = bool(out.get("expired"))
    out["expired_ts"] = max(0, int(out.get("expired_ts") or 0))
    out["expired_event_id"] = str(out.get("expired_event_id") or "")

    cleared = dict(out.get("cleared") or {})
    out["cleared"] = {
        "ts": max(0, int(cleared.get("ts") or 0)),
        "event_id": str(cleared.get("event_id") or ""),
        "chain_id": str(cleared.get("chain_id") or ""),
        "by": str(cleared.get("by") or ""),
        "reason": str(cleared.get("reason") or ""),
        "on_time": bool(cleared.get("on_time")) if ("on_time" in cleared) else False,
        "late": bool(cleared.get("late")) if ("late" in cleared) else False,
        "deadline_ts": max(0, int(cleared.get("deadline_ts") or 0)),
        "cleared_ts": max(0, int(cleared.get("cleared_ts") or 0)),
        "evidence_path": str(cleared.get("evidence_path") or ""),
        "evidence_sha256": str(cleared.get("evidence_sha256") or "").lower(),
        "evidence_schema": str(cleared.get("evidence_schema") or ""),
        "evidence_created_ts": max(0, int(cleared.get("evidence_created_ts") or 0)),
        "reviewer": str(cleared.get("reviewer") or ""),
        "evidence_summary": str(cleared.get("evidence_summary") or "")[:200],
        "evidence_note": str(cleared.get("evidence_note") or "")[:200],
        "evidence_sig_ok": bool(cleared.get("evidence_sig_ok")),
        "evidence_sig_alg": str(cleared.get("evidence_sig_alg") or ""),
        "evidence_sig_key_id": str(cleared.get("evidence_sig_key_id") or ""),
        "evidence_sig_error_code": str(cleared.get("evidence_sig_error_code") or ""),
        "evidence_payload_hash": str(cleared.get("evidence_payload_hash") or ""),
        "l4w_envelope_path": str(cleared.get("l4w_envelope_path") or ""),
        "l4w_envelope_sha256": str(cleared.get("l4w_envelope_sha256") or "").lower(),
        "l4w_envelope_hash": str(cleared.get("l4w_envelope_hash") or "").lower(),
        "l4w_prev_hash": str(cleared.get("l4w_prev_hash") or "").lower(),
        "l4w_pub_fingerprint": str(cleared.get("l4w_pub_fingerprint") or "").lower(),
    }
    return out


def _load_state(*, use_cache: bool) -> Dict[str, Dict[str, Any]]:
    global _STATE_CACHE, _STATE_CACHE_TS_MONO

    ttl = _ttl_sec()
    now_mono = time.monotonic()
    with _LOCK:
        if (
            use_cache
            and _STATE_CACHE is not None
            and (now_mono - _STATE_CACHE_TS_MONO) <= float(ttl)
        ):
            return {k: dict(v) for k, v in _STATE_CACHE.items()}

    p = _state_path()
    if not p.exists():
        data: Dict[str, Dict[str, Any]] = {}
    else:
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"quarantine_state_parse_error:{exc.__class__.__name__}")
        if not isinstance(raw, dict):
            raise RuntimeError("quarantine_state_invalid")
        data = {}
        for aid, row in raw.items():
            key = str(aid or "").strip()
            if not key or (not isinstance(row, dict)):
                continue
            data[key] = _normalize_state_entry(key, dict(row))

    with _LOCK:
        _STATE_CACHE = {k: dict(v) for k, v in data.items()}
        _STATE_CACHE_TS_MONO = now_mono
    return {k: dict(v) for k, v in data.items()}


def _compact_state(src: Dict[str, Dict[str, Any]], max_items: int) -> Dict[str, Dict[str, Any]]:
    if len(src) <= int(max_items):
        return src
    rows = sorted(
        ((aid, dict(row or {})) for aid, row in src.items()),
        key=lambda pair: int((pair[1] or {}).get("since_ts") or 0),
        reverse=True,
    )
    out: Dict[str, Dict[str, Any]] = {}
    for aid, row in rows[: int(max_items)]:
        out[aid] = row
    return out


def _save_state(src: Dict[str, Dict[str, Any]]) -> int:
    normalized: Dict[str, Dict[str, Any]] = {}
    for aid, row in dict(src or {}).items():
        key = str(aid or "").strip()
        if not key:
            continue
        normalized[key] = _normalize_state_entry(key, dict(row or {}))
    data = _compact_state(normalized, _max_state_items())
    root = _drift_root()
    root.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=True, indent=2)
    p = _state_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(p)

    with _LOCK:
        global _STATE_CACHE, _STATE_CACHE_TS_MONO
        _STATE_CACHE = {k: dict(v) for k, v in data.items()}
        _STATE_CACHE_TS_MONO = time.monotonic()
    return len(data)


def _append_event(row: Dict[str, Any]) -> None:
    root = _drift_root()
    root.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row or {}), ensure_ascii=True, separators=(",", ":"))
    with _events_path().open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _read_events_tail(limit_events: int, tail_lines: int) -> Tuple[List[Dict[str, Any]], int]:
    lines = _tail_lines(_events_path(), tail_lines)
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


def _state_row_defaults(agent_id: str) -> Dict[str, Any]:
    return {
        "agent_id": str(agent_id or ""),
        "active": False,
        "since_ts": 0,
        "event_id": "",
        "kind": "",
        "severity": "",
        "reason_code": "",
        "template_id": "",
        "caps_hash": "",
        "computed_hash": "",
        "stored_hash": "",
        "added": [],
        "removed": [],
        "last_seen_ts": 0,
        "challenge_open_ts": 0,
        "challenge_deadline_ts": 0,
        "challenge_sec": _challenge_sec(),
        "expired": False,
        "expired_ts": 0,
        "expired_event_id": "",
        "cleared": {
            "ts": 0,
            "event_id": "",
            "chain_id": "",
            "by": "",
            "reason": "",
            "on_time": False,
            "late": False,
            "deadline_ts": 0,
            "cleared_ts": 0,
            "evidence_path": "",
            "evidence_sha256": "",
            "evidence_schema": "",
            "evidence_created_ts": 0,
            "reviewer": "",
            "evidence_summary": "",
            "evidence_note": "",
            "evidence_sig_ok": False,
            "evidence_sig_alg": "",
            "evidence_sig_key_id": "",
            "evidence_sig_error_code": "",
            "evidence_payload_hash": "",
            "l4w_envelope_path": "",
            "l4w_envelope_sha256": "",
            "l4w_envelope_hash": "",
            "l4w_prev_hash": "",
            "l4w_pub_fingerprint": "",
        },
    }


def _evaluate_high_drift(agent_id: str, spec: Dict[str, Any], last_seen_row: Dict[str, Any]) -> Dict[str, Any]:
    template_id = str(spec.get("template_id") or "").strip()
    caps_effective = normalize_allowlist(spec.get("capabilities_effective") or [])
    caps_hash = _list_hash(caps_effective) if caps_effective else ""

    stored_allow = normalize_allowlist(spec.get("allowed_actions") or [])
    stored_hash = str(spec.get("allowed_actions_hash") or "").strip() or _list_hash(stored_allow)

    allow_rep = agent_factory.resolve_allowlist_for_spec(spec, slot_override="B")
    if not bool(allow_rep.get("ok")):
        raise RuntimeError(str(allow_rep.get("error_code") or "allowlist_resolve_failed"))

    computed_allow = normalize_allowlist(allow_rep.get("allowed_actions") or [])
    computed_hash = _list_hash(computed_allow)

    stored_extra = sorted(set(stored_allow) - set(computed_allow))[:10]
    stored_removed = sorted(set(computed_allow) - set(stored_allow))[:10]
    if stored_extra:
        reason_code = "TAMPER_SUSPECT"
        kind = "SPEC_MISMATCH"
        severity = "HIGH"
        eid = _event_id(agent_id, kind, reason_code, computed_hash, stored_hash)
        return {
            "active": True,
            "event_id": eid,
            "kind": kind,
            "severity": severity,
            "reason_code": reason_code,
            "template_id": template_id,
            "caps_hash": caps_hash,
            "computed_hash": computed_hash,
            "stored_hash": stored_hash,
            "added": stored_extra,
            "removed": stored_removed,
            "last_seen_ts": int(last_seen_row.get("ts") or 0),
        }

    prev_hash = str(last_seen_row.get("allowlist_hash") or "").strip()
    prev_allow = normalize_allowlist(last_seen_row.get("allowlist") or [])
    if prev_hash and prev_hash != computed_hash:
        added = sorted(set(computed_allow) - set(prev_allow))[:10]
        removed = sorted(set(prev_allow) - set(computed_allow))[:10]
        if added:
            reason_code = "ESCALATION"
            kind = "ALLOWLIST_CHANGED"
            severity = "HIGH"
            eid = _event_id(agent_id, kind, reason_code, computed_hash, stored_hash)
            return {
                "active": True,
                "event_id": eid,
                "kind": kind,
                "severity": severity,
                "reason_code": reason_code,
                "template_id": template_id,
                "caps_hash": caps_hash,
                "computed_hash": computed_hash,
                "stored_hash": stored_hash,
                "added": added,
                "removed": removed,
                "last_seen_ts": int(last_seen_row.get("ts") or 0),
            }

    return {
        "active": False,
        "event_id": "",
        "kind": "",
        "severity": "",
        "reason_code": "",
        "template_id": template_id,
        "caps_hash": caps_hash,
        "computed_hash": computed_hash,
        "stored_hash": stored_hash,
        "added": [],
        "removed": [],
        "last_seen_ts": int(last_seen_row.get("ts") or 0),
    }


def _set_event_row(
    *,
    event_type: str,
    agent_id: str,
    event_id: str,
    severity: str,
    reason_code: str,
    step: str,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "ts": int(time.time()),
        "type": str(event_type or ""),
        "agent_id": str(agent_id or ""),
        "event_id": str(event_id or ""),
        "severity": str(severity or ""),
        "reason_code": str(reason_code or ""),
        "step": str(step or ""),
        "details": dict(details or {}),
    }


def verify_evidence_packet(
    agent_id: str,
    event_id: str,
    evidence_path: str,
    evidence_sha256: str,
    *,
    sig_required: bool | None = None,
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    eid = str(event_id or "").strip()
    claimed = str(evidence_sha256 or "").strip().lower()
    eff_slot = _effective_slot()
    required = bool(sig_required) if (sig_required is not None) else bool(_evidence_sig_required(eff_slot))
    if not aid:
        return {"ok": False, "error_code": "AGENT_ID_REQUIRED", "error": "agent_id_required"}
    if not eid:
        return {"ok": False, "error_code": "EVENT_ID_REQUIRED", "error": "event_id_required"}
    if not claimed:
        return {"ok": False, "error_code": "EVIDENCE_HASH_REQUIRED", "error": "evidence_hash_required"}
    if len(claimed) != 64 or any(ch not in "0123456789abcdef" for ch in claimed):
        return {"ok": False, "error_code": "EVIDENCE_HASH_INVALID", "error": "evidence_hash_invalid"}

    path_rep = _resolve_evidence_path(evidence_path)
    if not bool(path_rep.get("ok")):
        return path_rep
    resolved_path = Path(str(path_rep.get("evidence_path") or "")).resolve()
    if not resolved_path.exists() or (not resolved_path.is_file()):
        return {
            "ok": False,
            "error_code": "EVIDENCE_NOT_FOUND",
            "error": "evidence_not_found",
            "evidence_path": str(resolved_path),
            "evidence_rel_path": str(path_rep.get("evidence_rel_path") or ""),
        }

    actual = _sha256_file(resolved_path).lower()
    if actual != claimed:
        return {
            "ok": False,
            "error_code": "EVIDENCE_HASH_MISMATCH",
            "error": "evidence_hash_mismatch",
            "evidence_path": str(resolved_path),
            "evidence_rel_path": str(path_rep.get("evidence_rel_path") or ""),
            "evidence_sha256": actual,
        }

    try:
        packet = json.loads(resolved_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "ok": False,
            "error_code": "EVIDENCE_JSON_INVALID",
            "error": "evidence_json_invalid",
            "evidence_path": str(resolved_path),
            "evidence_rel_path": str(path_rep.get("evidence_rel_path") or ""),
            "evidence_sha256": actual,
        }
    if not isinstance(packet, dict):
        return {
            "ok": False,
            "error_code": "EVIDENCE_SCHEMA_INVALID",
            "error": "evidence_schema_invalid",
            "evidence_path": str(resolved_path),
            "evidence_rel_path": str(path_rep.get("evidence_rel_path") or ""),
            "evidence_sha256": actual,
        }

    schema = str(packet.get("schema") or "")
    if schema != "ester.evidence.v1":
        return {
            "ok": False,
            "error_code": "EVIDENCE_SCHEMA_INVALID",
            "error": "evidence_schema_invalid",
            "evidence_schema": schema,
            "evidence_path": str(resolved_path),
            "evidence_rel_path": str(path_rep.get("evidence_rel_path") or ""),
            "evidence_sha256": actual,
        }

    packet_agent = str(packet.get("agent_id") or "")
    packet_event = str(packet.get("quarantine_event_id") or "")
    packet_decision = str(packet.get("decision") or "")
    if packet_agent != aid:
        return {
            "ok": False,
            "error_code": "EVIDENCE_AGENT_MISMATCH",
            "error": "evidence_agent_mismatch",
            "evidence_path": str(resolved_path),
            "evidence_rel_path": str(path_rep.get("evidence_rel_path") or ""),
            "evidence_sha256": actual,
            "evidence_schema": schema,
        }
    if packet_event != eid:
        return {
            "ok": False,
            "error_code": "EVIDENCE_EVENT_MISMATCH",
            "error": "evidence_event_mismatch",
            "evidence_path": str(resolved_path),
            "evidence_rel_path": str(path_rep.get("evidence_rel_path") or ""),
            "evidence_sha256": actual,
            "evidence_schema": schema,
        }
    if packet_decision != "CLEAR_QUARANTINE":
        return {
            "ok": False,
            "error_code": "EVIDENCE_DECISION_INVALID",
            "error": "evidence_decision_invalid",
            "evidence_path": str(resolved_path),
            "evidence_rel_path": str(path_rep.get("evidence_rel_path") or ""),
            "evidence_sha256": actual,
            "evidence_schema": schema,
        }

    try:
        created_ts = max(0, int(packet.get("created_ts") or 0))
    except Exception:
        created_ts = 0
    reviewer = str(packet.get("reviewer") or "").strip()
    summary = str(packet.get("summary") or "").strip()[:200]

    sig_ok = False
    sig_alg = ""
    sig_key_id = ""
    sig_error_code = ""
    sig_warning = ""
    payload_hash = ""
    if evidence_signing is None or (not bool(getattr(evidence_signing, "is_available", lambda: False)())):
        sig_error_code = "ED25519_UNAVAILABLE"
    else:
        verify_sig = evidence_signing.verify_packet(packet)
        sig_ok = bool(verify_sig.get("ok"))
        if sig_ok:
            sig_alg = str(verify_sig.get("alg") or "ed25519")
            sig_key_id = str(verify_sig.get("key_id") or "default")
            payload_hash = str(verify_sig.get("payload_hash") or "")
        else:
            sig_error_code = str(verify_sig.get("error_code") or "EVIDENCE_SIG_INVALID")
            sig_alg = str(verify_sig.get("alg") or "ed25519")
            sig_key_id = str(verify_sig.get("key_id") or "")
            payload_hash = str(verify_sig.get("payload_hash") or "")

    if required and (not sig_ok):
        return {
            "ok": False,
            "error_code": str(sig_error_code or "EVIDENCE_SIG_REQUIRED"),
            "error": str((str(sig_error_code or "") or "EVIDENCE_SIG_REQUIRED").lower()),
            "evidence_path": str(resolved_path),
            "evidence_rel_path": str(path_rep.get("evidence_rel_path") or ""),
            "evidence_sha256": actual,
            "evidence_schema": schema,
            "sig_ok": False,
            "sig_required": True,
            "sig_alg": str(sig_alg or "ed25519"),
            "sig_key_id": str(sig_key_id or ""),
            "sig_error_code": str(sig_error_code or "EVIDENCE_SIG_REQUIRED"),
            "payload_hash": str(payload_hash or ""),
        }

    if not sig_ok:
        code = str(sig_error_code or "EVIDENCE_SIG_REQUIRED")
        if code == "EVIDENCE_SIG_REQUIRED":
            sig_warning = "evidence_sig_missing"
        elif code == "ED25519_UNAVAILABLE":
            sig_warning = "evidence_sig_unavailable"
        else:
            sig_warning = "evidence_sig_invalid"

    return {
        "ok": True,
        "error_code": "",
        "evidence_path": str(resolved_path),
        "evidence_rel_path": str(path_rep.get("evidence_rel_path") or ""),
        "evidence_sha256": actual,
        "evidence_schema": schema,
        "created_ts": int(created_ts),
        "reviewer": reviewer,
        "summary": summary,
        "sig_ok": bool(sig_ok),
        "sig_required": bool(required),
        "sig_alg": str(sig_alg or ("ed25519" if sig_ok else "")),
        "sig_key_id": str(sig_key_id or ""),
        "sig_error_code": str(sig_error_code or ""),
        "sig_warning": str(sig_warning or ""),
        "payload_hash": str(payload_hash or ""),
    }


def _remaining_overdue(row: Dict[str, Any], now_ts: int) -> Tuple[int, int]:
    deadline = int(row.get("challenge_deadline_ts") or 0)
    if deadline <= 0:
        return 0, 0
    diff = deadline - int(now_ts)
    if diff >= 0:
        return int(diff), 0
    return 0, abs(int(diff))


def maybe_mark_expired(agent_id: str, *, now_ts: int | None = None) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return {"ok": False, "error": "agent_id_required", "error_code": "AGENT_ID_REQUIRED"}
    ts = int(now_ts if now_ts is not None else time.time())
    state = _load_state(use_cache=False)
    row = _normalize_state_entry(aid, dict(state.get(aid) or _state_row_defaults(aid)))
    if not bool(row.get("active")):
        return {
            "ok": True,
            "changed": False,
            "active": False,
            "expired": bool(row.get("expired")),
            "event_id": str(row.get("event_id") or ""),
        }

    deadline = int(row.get("challenge_deadline_ts") or 0)
    if deadline <= 0:
        deadline = int(row.get("challenge_open_ts") or ts) + int(row.get("challenge_sec") or _challenge_sec())
        row["challenge_deadline_ts"] = deadline

    current_event_id = str(row.get("event_id") or "")
    expired_event_id = str(row.get("expired_event_id") or "")
    if ts <= deadline:
        if bool(row.get("expired")) and expired_event_id != current_event_id:
            row["expired"] = False
            row["expired_ts"] = 0
            row["expired_event_id"] = ""
            state[aid] = row
            _save_state(state)
            return {
                "ok": True,
                "changed": True,
                "active": True,
                "expired": False,
                "event_id": current_event_id,
                "deadline_ts": deadline,
                "remaining_sec": max(0, deadline - ts),
                "overdue_sec": 0,
            }
        return {
            "ok": True,
            "changed": False,
            "active": True,
            "expired": bool(row.get("expired")),
            "event_id": current_event_id,
            "deadline_ts": deadline,
            "remaining_sec": max(0, deadline - ts),
            "overdue_sec": 0,
        }

    overdue = max(0, ts - deadline)
    if expired_event_id == current_event_id:
        if not bool(row.get("expired")):
            row["expired"] = True
            row["expired_ts"] = int(row.get("expired_ts") or ts)
            state[aid] = row
            _save_state(state)
            return {
                "ok": True,
                "changed": True,
                "active": True,
                "expired": True,
                "event_id": current_event_id,
                "deadline_ts": deadline,
                "remaining_sec": 0,
                "overdue_sec": overdue,
            }
        return {
            "ok": True,
            "changed": False,
            "active": True,
            "expired": True,
            "event_id": current_event_id,
            "deadline_ts": deadline,
            "remaining_sec": 0,
            "overdue_sec": overdue,
        }

    row["expired"] = True
    row["expired_ts"] = ts
    row["expired_event_id"] = current_event_id
    state[aid] = row
    _save_state(state)
    _append_event(
        _set_event_row(
            event_type="QUARANTINE_EXPIRED",
            agent_id=aid,
            event_id=current_event_id,
            severity=str(row.get("severity") or "HIGH"),
            reason_code="CHALLENGE_WINDOW_EXPIRED",
            step="quarantine.challenge",
            details={"deadline_ts": int(deadline), "overdue_sec": int(overdue)},
        )
    )
    return {
        "ok": True,
        "changed": True,
        "active": True,
        "expired": True,
        "event_id": current_event_id,
        "deadline_ts": deadline,
        "remaining_sec": 0,
        "overdue_sec": overdue,
    }


def ensure_quarantine_for_agent(agent_id: str, *, source: str) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    raw_slot = _slot()
    eff_slot = _effective_slot()
    enforced = bool(eff_slot == "B")
    fail_max = _fail_max()
    fail_state = _failure_snapshot(fail_max)

    if not aid:
        return {
            "ok": False,
            "active": bool(enforced),
            "enforced": bool(enforced),
            "slot": eff_slot,
            "error_code": "AGENT_ID_REQUIRED",
            "error": "agent_id_required",
            "event_id": "",
            "reason_code": ("QUARANTINE_UNAVAILABLE" if enforced else "AGENT_ID_REQUIRED"),
            "severity": ("HIGH" if enforced else ""),
        }

    try:
        state = _load_state(use_cache=False)
        row = _normalize_state_entry(aid, dict(state.get(aid) or _state_row_defaults(aid)))
        if bool(row.get("active")):
            exp_rep = maybe_mark_expired(aid)
            state = _load_state(use_cache=False)
            row = _normalize_state_entry(aid, dict(state.get(aid) or row))
            now_ts = int(time.time())
            remaining_sec, overdue_sec = _remaining_overdue(row, now_ts)
            _note_success()
            return {
                "ok": True,
                "active": True,
                "enforced": bool(enforced),
                "slot": eff_slot,
                "event_id": str(row.get("event_id") or ""),
                "reason_code": str(row.get("reason_code") or ""),
                "severity": str(row.get("severity") or ""),
                "kind": str(row.get("kind") or ""),
                "degraded": bool(eff_slot != raw_slot),
                "mode_forced": str(fail_state.get("mode_forced") or ""),
                "challenge_open_ts": int(row.get("challenge_open_ts") or 0),
                "challenge_deadline_ts": int(row.get("challenge_deadline_ts") or 0),
                "challenge_sec": int(row.get("challenge_sec") or _challenge_sec()),
                "expired": bool(row.get("expired")),
                "expired_ts": int(row.get("expired_ts") or 0),
                "expired_event_id": str(row.get("expired_event_id") or ""),
                "challenge_remaining_sec": int(remaining_sec),
                "overdue_sec": int(overdue_sec),
                "expire_changed": bool(exp_rep.get("changed")),
                "details": {
                    "template_id": str(row.get("template_id") or ""),
                    "added": list(row.get("added") or []),
                    "removed": list(row.get("removed") or []),
                },
            }

        rep = agent_factory.get_agent(aid)
        if not bool(rep.get("ok")):
            raise RuntimeError("agent_not_found")
        spec = dict((rep.get("agent") or {}).get("spec") or {})
        if not spec:
            raise RuntimeError("spec_missing")

        last_seen = _load_last_seen()
        drift = _evaluate_high_drift(aid, spec, dict(last_seen.get(aid) or {}))

        if bool(drift.get("active")):
            drift_event_id = str(drift.get("event_id") or "")
            cleared = dict(row.get("cleared") or {})
            cleared_event = str(cleared.get("event_id") or "")
            if (not bool(row.get("active"))) and cleared_event and (cleared_event == drift_event_id):
                _note_success()
                return {
                    "ok": True,
                    "active": False,
                    "enforced": bool(enforced),
                    "slot": eff_slot,
                    "event_id": drift_event_id,
                    "reason_code": str(drift.get("reason_code") or ""),
                    "severity": str(drift.get("severity") or ""),
                    "kind": str(drift.get("kind") or ""),
                    "acknowledged": True,
                    "degraded": bool(eff_slot != raw_slot),
                    "mode_forced": str(fail_state.get("mode_forced") or ""),
                }

            next_row = _state_row_defaults(aid)
            now_set = int(time.time())
            challenge_sec = int(_challenge_sec())
            next_row.update(
                {
                    "agent_id": aid,
                    "active": True,
                    "since_ts": int(now_set),
                    "event_id": drift_event_id,
                    "kind": str(drift.get("kind") or ""),
                    "severity": str(drift.get("severity") or "HIGH"),
                    "reason_code": str(drift.get("reason_code") or ""),
                    "template_id": str(drift.get("template_id") or ""),
                    "caps_hash": str(drift.get("caps_hash") or ""),
                    "computed_hash": str(drift.get("computed_hash") or ""),
                    "stored_hash": str(drift.get("stored_hash") or ""),
                    "added": [str(x) for x in list(drift.get("added") or [])[:10] if str(x).strip()],
                    "removed": [str(x) for x in list(drift.get("removed") or [])[:10] if str(x).strip()],
                    "last_seen_ts": int(drift.get("last_seen_ts") or 0),
                    "challenge_open_ts": int(now_set),
                    "challenge_deadline_ts": int(now_set + challenge_sec),
                    "challenge_sec": int(challenge_sec),
                    "expired": False,
                    "expired_ts": 0,
                    "expired_event_id": "",
                    "cleared": dict(row.get("cleared") or _state_row_defaults(aid).get("cleared") or {}),
                }
            )
            changed = bool(
                (not bool(row.get("active")))
                or (str(row.get("event_id") or "") != str(next_row.get("event_id") or ""))
                or (str(row.get("reason_code") or "") != str(next_row.get("reason_code") or ""))
            )
            if changed:
                state[aid] = next_row
                _save_state(state)
                _append_event(
                    _set_event_row(
                        event_type="QUARANTINE_SET",
                        agent_id=aid,
                        event_id=str(next_row.get("event_id") or ""),
                        severity=str(next_row.get("severity") or ""),
                        reason_code=str(next_row.get("reason_code") or ""),
                        step=str(source or "ensure"),
                        details={
                            "kind": str(next_row.get("kind") or ""),
                            "template_id": str(next_row.get("template_id") or ""),
                            "added": list(next_row.get("added") or []),
                            "removed": list(next_row.get("removed") or []),
                        },
                    )
                )
            _note_success()
            now_ts = int(time.time())
            remaining_sec, overdue_sec = _remaining_overdue(next_row, now_ts)
            return {
                "ok": True,
                "active": True,
                "enforced": bool(enforced),
                "slot": eff_slot,
                "event_id": str(next_row.get("event_id") or ""),
                "reason_code": str(next_row.get("reason_code") or ""),
                "severity": str(next_row.get("severity") or ""),
                "kind": str(next_row.get("kind") or ""),
                "degraded": bool(eff_slot != raw_slot),
                "mode_forced": str(fail_state.get("mode_forced") or ""),
                "challenge_open_ts": int(next_row.get("challenge_open_ts") or 0),
                "challenge_deadline_ts": int(next_row.get("challenge_deadline_ts") or 0),
                "challenge_sec": int(next_row.get("challenge_sec") or _challenge_sec()),
                "expired": bool(next_row.get("expired")),
                "expired_ts": int(next_row.get("expired_ts") or 0),
                "expired_event_id": str(next_row.get("expired_event_id") or ""),
                "challenge_remaining_sec": int(remaining_sec),
                "overdue_sec": int(overdue_sec),
                "details": {
                    "template_id": str(next_row.get("template_id") or ""),
                    "added": list(next_row.get("added") or []),
                    "removed": list(next_row.get("removed") or []),
                },
            }

        _note_success()
        return {
            "ok": True,
            "active": False,
            "enforced": bool(enforced),
            "slot": eff_slot,
            "event_id": "",
            "reason_code": "",
            "severity": "",
            "kind": "",
            "degraded": bool(eff_slot != raw_slot),
            "mode_forced": str(fail_state.get("mode_forced") or ""),
        }
    except Exception as exc:
        err = f"quarantine_error:{exc.__class__.__name__}"
        if raw_slot == "B":
            fail_state = _note_failure(err, fail_max)
            eff_slot_after = _effective_slot()
            enforced_after = bool(eff_slot_after == "B")
            return {
                "ok": False,
                "active": bool(enforced_after),
                "enforced": bool(enforced_after),
                "slot": eff_slot_after,
                "event_id": "",
                "reason_code": ("QUARANTINE_UNAVAILABLE" if enforced_after else ""),
                "severity": ("HIGH" if enforced_after else ""),
                "kind": "QUARANTINE_SYSTEM",
                "error_code": "QUARANTINE_UNAVAILABLE",
                "error": err,
                "degraded": bool(eff_slot_after != raw_slot),
                "mode_forced": str(fail_state.get("mode_forced") or ""),
                "last_rollback_reason": str(fail_state.get("last_rollback_reason") or ""),
            }
        return {
            "ok": False,
            "active": False,
            "enforced": False,
            "slot": eff_slot,
            "event_id": "",
            "reason_code": "",
            "severity": "",
            "kind": "",
            "error_code": "QUARANTINE_UNAVAILABLE",
            "error": err,
            "degraded": False,
            "mode_forced": str(fail_state.get("mode_forced") or ""),
            "last_rollback_reason": str(fail_state.get("last_rollback_reason") or ""),
        }


def is_quarantined(agent_id: str) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    eff_slot = _effective_slot()
    fail_state = _failure_snapshot(_fail_max())
    if not aid:
        return {
            "ok": False,
            "active": False,
            "slot": eff_slot,
            "enforced": bool(eff_slot == "B"),
            "error_code": "AGENT_ID_REQUIRED",
            "error": "agent_id_required",
        }
    try:
        _ = maybe_mark_expired(aid)
        state = _load_state(use_cache=True)
        row = _normalize_state_entry(aid, dict(state.get(aid) or {}))
        active = bool(row.get("active"))
        now_ts = int(time.time())
        remaining_sec, overdue_sec = _remaining_overdue(row, now_ts)
        return {
            "ok": True,
            "active": active,
            "slot": eff_slot,
            "enforced": bool(eff_slot == "B"),
            "event_id": str(row.get("event_id") or ""),
            "reason_code": str(row.get("reason_code") or ""),
            "severity": str(row.get("severity") or ""),
            "kind": str(row.get("kind") or ""),
            "since_ts": int(row.get("since_ts") or 0),
            "challenge_open_ts": int(row.get("challenge_open_ts") or 0),
            "challenge_deadline_ts": int(row.get("challenge_deadline_ts") or 0),
            "challenge_sec": int(row.get("challenge_sec") or _challenge_sec()),
            "expired": bool(row.get("expired")),
            "expired_ts": int(row.get("expired_ts") or 0),
            "expired_event_id": str(row.get("expired_event_id") or ""),
            "challenge_remaining_sec": int(remaining_sec),
            "overdue_sec": int(overdue_sec),
            "degraded": bool(eff_slot != _slot()),
            "mode_forced": str(fail_state.get("mode_forced") or ""),
        }
    except Exception as exc:
        err = f"quarantine_state_error:{exc.__class__.__name__}"
        if _slot() == "B":
            fail_state = _note_failure(err, _fail_max())
            eff_slot = _effective_slot()
            if eff_slot == "B":
                return {
                    "ok": False,
                    "active": True,
                    "slot": "B",
                    "enforced": True,
                    "event_id": "",
                    "reason_code": "QUARANTINE_UNAVAILABLE",
                    "severity": "HIGH",
                    "kind": "QUARANTINE_SYSTEM",
                    "error_code": "QUARANTINE_UNAVAILABLE",
                    "error": err,
                    "mode_forced": str(fail_state.get("mode_forced") or ""),
                }
        return {
            "ok": False,
            "active": False,
            "slot": _effective_slot(),
            "enforced": bool(_effective_slot() == "B"),
            "event_id": "",
            "reason_code": "",
            "severity": "",
            "kind": "",
            "error_code": "QUARANTINE_UNAVAILABLE",
            "error": err,
        }


def clear_quarantine(
    agent_id: str,
    event_id: str,
    chain_id: str,
    by: str,
    reason: str = "",
    *,
    evidence: Dict[str, Any] | None = None,
    evidence_note: str = "",
    l4w: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    eid = str(event_id or "").strip()
    chain = str(chain_id or "").strip()
    actor = str(by or "").strip()
    why = str(reason or "").strip()
    raw_slot = _slot()
    eff_slot = _effective_slot()
    enforced = bool(eff_slot == "B")
    fail_max = _fail_max()
    fail_state = _failure_snapshot(fail_max)
    if not aid:
        return {"ok": False, "error": "agent_id_required", "error_code": "AGENT_ID_REQUIRED"}
    if not eid:
        return {"ok": False, "error": "event_id_required", "error_code": "EVENT_ID_REQUIRED"}
    if not why:
        return {"ok": False, "error": "reason_required", "error_code": "REASON_REQUIRED"}

    evidence_raw = dict(evidence or {})
    evidence_path_raw = str(evidence_raw.get("path") or "").strip()
    evidence_sha_raw = str(evidence_raw.get("sha256") or "").strip().lower()
    evidence_note_norm = str(evidence_note or "").strip()[:200]
    l4w_raw = dict(l4w or {})
    l4w_path_raw = str(l4w_raw.get("envelope_path") or "").strip()
    l4w_sha_raw = str(l4w_raw.get("envelope_sha256") or "").strip().lower()

    state = _load_state(use_cache=False)
    row = dict(state.get(aid) or _state_row_defaults(aid))
    if not bool(row.get("active")):
        return {
            "ok": False,
            "error": "not_quarantined",
            "error_code": "NOT_QUARANTINED",
            "agent_id": aid,
            "event_id": str(row.get("event_id") or ""),
        }
    current_eid = str(row.get("event_id") or "")
    if current_eid != eid:
        return {
            "ok": False,
            "error": "event_mismatch",
            "error_code": "EVENT_MISMATCH",
            "agent_id": aid,
            "event_id": current_eid,
            "expected_event_id": current_eid,
            "provided_event_id": eid,
        }

    warnings: List[str] = []
    evidence_info = {
        "evidence_path": "",
        "evidence_sha256": "",
        "evidence_schema": "",
        "evidence_created_ts": 0,
        "reviewer": "",
        "evidence_summary": "",
        "evidence_note": evidence_note_norm,
        "evidence_sig_ok": False,
        "evidence_sig_alg": "",
        "evidence_sig_key_id": "",
        "evidence_sig_error_code": "",
        "evidence_payload_hash": "",
    }

    def _evidence_failure(rep: Dict[str, Any]) -> Dict[str, Any]:
        code = str(rep.get("error_code") or "EVIDENCE_INVALID")
        err = str(rep.get("error") or "evidence_invalid")
        out = {
            "ok": False,
            "error": err,
            "error_code": code,
            "agent_id": aid,
            "event_id": current_eid,
            "slot": eff_slot,
            "enforced": bool(enforced),
            "degraded": bool(eff_slot != raw_slot),
            "mode_forced": str(fail_state.get("mode_forced") or ""),
            "last_rollback_reason": str(fail_state.get("last_rollback_reason") or ""),
            "evidence_path": str(rep.get("evidence_rel_path") or rep.get("evidence_path") or evidence_path_raw),
            "evidence_sha256": str(evidence_sha_raw or rep.get("evidence_sha256") or ""),
            "evidence_sig_ok": bool(rep.get("sig_ok")),
            "evidence_sig_alg": str(rep.get("sig_alg") or ""),
            "evidence_sig_key_id": str(rep.get("sig_key_id") or ""),
            "evidence_sig_error_code": str(rep.get("sig_error_code") or rep.get("error_code") or ""),
            "evidence_payload_hash": str(rep.get("payload_hash") or ""),
            "l4w_envelope_path": str(l4w_path_raw or ""),
            "l4w_envelope_sha256": str(l4w_sha_raw or ""),
            "l4w_envelope_hash": "",
            "l4w_prev_hash": "",
            "l4w_pub_fingerprint": "",
        }
        if raw_slot == "B" and enforced:
            fail_limit = 1 if code == "ED25519_UNAVAILABLE" else fail_max
            fail_after = _note_failure("evidence_verify_error:" + code, fail_limit)
            eff_after = _effective_slot()
            out["slot"] = eff_after
            out["enforced"] = bool(eff_after == "B")
            out["degraded"] = bool(eff_after != raw_slot)
            out["mode_forced"] = str(fail_after.get("mode_forced") or "")
            out["last_rollback_reason"] = str(fail_after.get("last_rollback_reason") or "")
        return out

    l4w_info = {
        "l4w_envelope_path": "",
        "l4w_envelope_sha256": "",
        "l4w_envelope_hash": "",
        "l4w_prev_hash": "",
        "l4w_pub_fingerprint": "",
    }

    def _l4w_failure(rep: Dict[str, Any]) -> Dict[str, Any]:
        code = str(rep.get("error_code") or "L4W_SCHEMA_INVALID")
        err = str(rep.get("error") or "l4w_invalid")
        out = {
            "ok": False,
            "error": err,
            "error_code": code,
            "agent_id": aid,
            "event_id": current_eid,
            "slot": eff_slot,
            "enforced": bool(enforced),
            "degraded": bool(eff_slot != raw_slot),
            "mode_forced": str(fail_state.get("mode_forced") or ""),
            "last_rollback_reason": str(fail_state.get("last_rollback_reason") or ""),
            "evidence_path": str(evidence_info.get("evidence_path") or evidence_path_raw),
            "evidence_sha256": str(evidence_info.get("evidence_sha256") or evidence_sha_raw),
            "l4w_envelope_path": str(rep.get("l4w_envelope_path") or l4w_path_raw),
            "l4w_envelope_sha256": str(rep.get("l4w_envelope_sha256") or l4w_sha_raw),
            "l4w_envelope_hash": str(rep.get("l4w_envelope_hash") or ""),
            "l4w_prev_hash": str(rep.get("l4w_prev_hash") or ""),
            "l4w_pub_fingerprint": str(rep.get("l4w_pub_fingerprint") or ""),
        }
        if raw_slot == "B" and enforced:
            fail_limit = 1 if code == "ED25519_UNAVAILABLE" else fail_max
            fail_after = _note_failure("l4w_verify_error:" + code, fail_limit)
            eff_after = _effective_slot()
            out["slot"] = eff_after
            out["enforced"] = bool(eff_after == "B")
            out["degraded"] = bool(eff_after != raw_slot)
            out["mode_forced"] = str(fail_after.get("mode_forced") or "")
            out["last_rollback_reason"] = str(fail_after.get("last_rollback_reason") or "")
        return out

    def _verify_l4w_once(*, chain_enforced: bool) -> Dict[str, Any]:
        if l4w_witness is None:
            return {"ok": False, "error_code": "L4W_SCHEMA_INVALID", "error": "l4w_unavailable"}
        if (not l4w_path_raw) or (not l4w_sha_raw):
            return {"ok": False, "error_code": "L4W_REQUIRED", "error": "l4w_required"}
        if len(l4w_sha_raw) != 64:
            return {"ok": False, "error_code": "L4W_HASH_MISMATCH", "error": "l4w_hash_invalid"}

        path_rep = l4w_witness.resolve_envelope_path(l4w_path_raw)
        if not bool(path_rep.get("ok")):
            return {
                "ok": False,
                "error_code": str(path_rep.get("error_code") or "L4W_PATH_FORBIDDEN"),
                "error": str(path_rep.get("error") or "l4w_path_forbidden"),
                "l4w_envelope_path": str(path_rep.get("envelope_rel_path") or l4w_path_raw),
            }
        resolved = Path(str(path_rep.get("envelope_path") or "")).resolve()
        rel_path = str(path_rep.get("envelope_rel_path") or "").replace("\\", "/")
        if (not resolved.exists()) or (not resolved.is_file()):
            return {
                "ok": False,
                "error_code": "L4W_SCHEMA_INVALID",
                "error": "l4w_not_found",
                "l4w_envelope_path": rel_path,
            }

        actual_sha = str(l4w_witness.sha256_file(resolved) or "").strip().lower()
        if actual_sha != l4w_sha_raw:
            return {
                "ok": False,
                "error_code": "L4W_HASH_MISMATCH",
                "error": "l4w_hash_mismatch",
                "l4w_envelope_path": rel_path,
                "l4w_envelope_sha256": actual_sha,
            }

        try:
            envelope_obj = json.loads(resolved.read_text(encoding="utf-8"))
        except Exception:
            return {
                "ok": False,
                "error_code": "L4W_SCHEMA_INVALID",
                "error": "l4w_json_invalid",
                "l4w_envelope_path": rel_path,
                "l4w_envelope_sha256": actual_sha,
            }
        if not isinstance(envelope_obj, dict):
            return {
                "ok": False,
                "error_code": "L4W_SCHEMA_INVALID",
                "error": "l4w_schema_invalid",
                "l4w_envelope_path": rel_path,
                "l4w_envelope_sha256": actual_sha,
            }
        if str(envelope_obj.get("schema") or "") != "ester.l4w.envelope.v1":
            return {
                "ok": False,
                "error_code": "L4W_SCHEMA_INVALID",
                "error": "l4w_schema_invalid",
                "l4w_envelope_path": rel_path,
                "l4w_envelope_sha256": actual_sha,
            }

        verify = l4w_witness.verify_envelope(envelope_obj)
        if not bool(verify.get("ok")):
            return {
                "ok": False,
                "error_code": str(verify.get("error_code") or "L4W_SIG_INVALID"),
                "error": str(verify.get("error") or "l4w_sig_invalid"),
                "l4w_envelope_path": rel_path,
                "l4w_envelope_sha256": actual_sha,
                "l4w_envelope_hash": str(verify.get("envelope_hash") or ""),
            }

        subject = dict(envelope_obj.get("subject") or {})
        env_agent_id = str(subject.get("agent_id") or "").strip()
        env_event_id = str(subject.get("quarantine_event_id") or "").strip()
        if env_agent_id != aid or env_event_id != current_eid:
            return {
                "ok": False,
                "error_code": "L4W_SUBJECT_MISMATCH",
                "error": "l4w_subject_mismatch",
                "l4w_envelope_path": rel_path,
                "l4w_envelope_sha256": actual_sha,
                "l4w_envelope_hash": str(verify.get("envelope_hash") or ""),
                "subject_agent_id": env_agent_id,
                "subject_event_id": env_event_id,
            }

        evidence_ref = dict(envelope_obj.get("evidence_ref") or {})
        env_path = str(evidence_ref.get("path") or "").strip().replace("\\", "/")
        env_sha = str(evidence_ref.get("sha256") or "").strip().lower()
        evidence_path_now = str(evidence_info.get("evidence_path") or "").strip().replace("\\", "/")
        evidence_sha_now = str(evidence_info.get("evidence_sha256") or "").strip().lower()
        if env_path != evidence_path_now or env_sha != evidence_sha_now:
            return {
                "ok": False,
                "error_code": "L4W_EVIDENCE_REF_MISMATCH",
                "error": "l4w_evidence_ref_mismatch",
                "l4w_envelope_path": rel_path,
                "l4w_envelope_sha256": actual_sha,
                "l4w_envelope_hash": str(verify.get("envelope_hash") or ""),
                "l4w_prev_hash": str((dict(envelope_obj.get("chain") or {})).get("prev_hash") or "").strip().lower(),
            }

        env_chain = dict(envelope_obj.get("chain") or {})
        prev_hash = str(env_chain.get("prev_hash") or "").strip().lower()
        chain_check = l4w_witness.verify_chain_prev_hash(aid, prev_hash)
        if not bool(chain_check.get("ok")):
            out = {
                "ok": False,
                "error_code": "L4W_CHAIN_BROKEN",
                "error": "l4w_chain_broken",
                "l4w_envelope_path": rel_path,
                "l4w_envelope_sha256": actual_sha,
                "l4w_envelope_hash": str(verify.get("envelope_hash") or ""),
                "l4w_prev_hash": prev_hash,
            }
            if not chain_enforced:
                out["warn_only"] = True
            return out

        append = l4w_witness.append_chain_record(
            aid,
            quarantine_event_id=current_eid,
            envelope_id=str(envelope_obj.get("envelope_id") or ""),
            envelope_hash=str(verify.get("envelope_hash") or ""),
            prev_hash=prev_hash,
            envelope_path=rel_path,
            envelope_sha256=actual_sha,
            ts=int(envelope_obj.get("ts") or int(time.time())),
        )
        if not bool(append.get("ok")):
            out = {
                "ok": False,
                "error_code": str(append.get("error_code") or "L4W_CHAIN_BROKEN"),
                "error": str(append.get("error") or "l4w_chain_broken"),
                "l4w_envelope_path": rel_path,
                "l4w_envelope_sha256": actual_sha,
                "l4w_envelope_hash": str(verify.get("envelope_hash") or ""),
                "l4w_prev_hash": prev_hash,
            }
            if not chain_enforced:
                out["warn_only"] = True
            return out

        return {
            "ok": True,
            "l4w_envelope_path": rel_path,
            "l4w_envelope_sha256": actual_sha,
            "l4w_envelope_hash": str(verify.get("envelope_hash") or ""),
            "l4w_prev_hash": prev_hash,
            "l4w_pub_fingerprint": str(verify.get("pub_fingerprint") or ""),
        }

    if enforced:
        if (not evidence_path_raw) or (not evidence_sha_raw):
            return _evidence_failure({"error_code": "EVIDENCE_REQUIRED", "error": "evidence_required"})
        verify = verify_evidence_packet(aid, current_eid, evidence_path_raw, evidence_sha_raw, sig_required=True)
        if not bool(verify.get("ok")):
            return _evidence_failure(verify)
        evidence_info["evidence_path"] = str(verify.get("evidence_rel_path") or verify.get("evidence_path") or "")
        evidence_info["evidence_sha256"] = str(verify.get("evidence_sha256") or "")
        evidence_info["evidence_schema"] = str(verify.get("evidence_schema") or "")
        evidence_info["evidence_created_ts"] = int(verify.get("created_ts") or 0)
        evidence_info["reviewer"] = str(verify.get("reviewer") or "")
        evidence_info["evidence_summary"] = str(verify.get("summary") or "")[:200]
        evidence_info["evidence_sig_ok"] = bool(verify.get("sig_ok"))
        evidence_info["evidence_sig_alg"] = str(verify.get("sig_alg") or "")
        evidence_info["evidence_sig_key_id"] = str(verify.get("sig_key_id") or "")
        evidence_info["evidence_sig_error_code"] = str(verify.get("sig_error_code") or "")
        evidence_info["evidence_payload_hash"] = str(verify.get("payload_hash") or "")
    else:
        if (not evidence_path_raw) or (not evidence_sha_raw):
            warnings.append("evidence_missing")
        else:
            verify = verify_evidence_packet(aid, current_eid, evidence_path_raw, evidence_sha_raw, sig_required=False)
            if bool(verify.get("ok")):
                evidence_info["evidence_path"] = str(verify.get("evidence_rel_path") or verify.get("evidence_path") or "")
                evidence_info["evidence_sha256"] = str(verify.get("evidence_sha256") or "")
                evidence_info["evidence_schema"] = str(verify.get("evidence_schema") or "")
                evidence_info["evidence_created_ts"] = int(verify.get("created_ts") or 0)
                evidence_info["reviewer"] = str(verify.get("reviewer") or "")
                evidence_info["evidence_summary"] = str(verify.get("summary") or "")[:200]
                evidence_info["evidence_sig_ok"] = bool(verify.get("sig_ok"))
                evidence_info["evidence_sig_alg"] = str(verify.get("sig_alg") or "")
                evidence_info["evidence_sig_key_id"] = str(verify.get("sig_key_id") or "")
                evidence_info["evidence_sig_error_code"] = str(verify.get("sig_error_code") or "")
                evidence_info["evidence_payload_hash"] = str(verify.get("payload_hash") or "")
                if str(verify.get("sig_warning") or "").strip():
                    warnings.append(str(verify.get("sig_warning") or ""))
            else:
                warnings.append("evidence_invalid:" + str(verify.get("error_code") or "EVIDENCE_INVALID"))
                evidence_info["evidence_path"] = str(verify.get("evidence_rel_path") or evidence_path_raw)
                evidence_info["evidence_sha256"] = str(evidence_sha_raw)

    l4w_required = bool(_l4w_required(eff_slot))
    chain_required = bool(_l4w_chain_enforced(eff_slot))
    if enforced and l4w_required:
        verify_l4w = _verify_l4w_once(chain_enforced=chain_required)
        if not bool(verify_l4w.get("ok")):
            if (not chain_required) and bool(verify_l4w.get("warn_only")):
                warnings.append("chain_disabled")
            else:
                return _l4w_failure(verify_l4w)
        if bool(verify_l4w.get("ok")):
            l4w_info["l4w_envelope_path"] = str(verify_l4w.get("l4w_envelope_path") or "")
            l4w_info["l4w_envelope_sha256"] = str(verify_l4w.get("l4w_envelope_sha256") or "")
            l4w_info["l4w_envelope_hash"] = str(verify_l4w.get("l4w_envelope_hash") or "")
            l4w_info["l4w_prev_hash"] = str(verify_l4w.get("l4w_prev_hash") or "")
            l4w_info["l4w_pub_fingerprint"] = str(verify_l4w.get("l4w_pub_fingerprint") or "")
    elif enforced and (not l4w_required):
        warnings.append("l4w_disabled")
    else:
        if (not l4w_path_raw) or (not l4w_sha_raw):
            warnings.append("l4w_missing")
        else:
            verify_l4w = _verify_l4w_once(chain_enforced=False)
            if bool(verify_l4w.get("ok")):
                l4w_info["l4w_envelope_path"] = str(verify_l4w.get("l4w_envelope_path") or "")
                l4w_info["l4w_envelope_sha256"] = str(verify_l4w.get("l4w_envelope_sha256") or "")
                l4w_info["l4w_envelope_hash"] = str(verify_l4w.get("l4w_envelope_hash") or "")
                l4w_info["l4w_prev_hash"] = str(verify_l4w.get("l4w_prev_hash") or "")
                l4w_info["l4w_pub_fingerprint"] = str(verify_l4w.get("l4w_pub_fingerprint") or "")
            elif bool(verify_l4w.get("warn_only")):
                warnings.append("l4w_chain_broken_observe_only")
            else:
                warnings.append("l4w_invalid:" + str(verify_l4w.get("error_code") or "L4W_SCHEMA_INVALID"))

    prev_active = bool(row.get("active"))
    now_ts = int(time.time())
    deadline_ts = int(row.get("challenge_deadline_ts") or 0)
    on_time = bool(deadline_ts > 0 and now_ts <= deadline_ts)
    late = bool(deadline_ts > 0 and now_ts > deadline_ts)
    row["active"] = False
    row["cleared"] = {
        "ts": int(now_ts),
        "event_id": current_eid,
        "chain_id": chain,
        "by": actor,
        "reason": why,
        "on_time": bool(on_time),
        "late": bool(late),
        "deadline_ts": int(deadline_ts),
        "cleared_ts": int(now_ts),
        "evidence_path": str(evidence_info.get("evidence_path") or ""),
        "evidence_sha256": str(evidence_info.get("evidence_sha256") or ""),
        "evidence_schema": str(evidence_info.get("evidence_schema") or ""),
        "evidence_created_ts": int(evidence_info.get("evidence_created_ts") or 0),
        "reviewer": str(evidence_info.get("reviewer") or ""),
        "evidence_summary": str(evidence_info.get("evidence_summary") or "")[:200],
        "evidence_note": str(evidence_info.get("evidence_note") or "")[:200],
        "evidence_sig_ok": bool(evidence_info.get("evidence_sig_ok")),
        "evidence_sig_alg": str(evidence_info.get("evidence_sig_alg") or ""),
        "evidence_sig_key_id": str(evidence_info.get("evidence_sig_key_id") or ""),
        "evidence_sig_error_code": str(evidence_info.get("evidence_sig_error_code") or ""),
        "evidence_payload_hash": str(evidence_info.get("evidence_payload_hash") or ""),
        "l4w_envelope_path": str(l4w_info.get("l4w_envelope_path") or ""),
        "l4w_envelope_sha256": str(l4w_info.get("l4w_envelope_sha256") or ""),
        "l4w_envelope_hash": str(l4w_info.get("l4w_envelope_hash") or ""),
        "l4w_prev_hash": str(l4w_info.get("l4w_prev_hash") or ""),
        "l4w_pub_fingerprint": str(l4w_info.get("l4w_pub_fingerprint") or ""),
    }
    state[aid] = row
    _save_state(state)

    clear_details = {
        "chain_id": chain,
        "by": actor,
        "reason": why,
        "on_time": bool(on_time),
        "late": bool(late),
        "deadline_ts": int(deadline_ts),
        "cleared_ts": int(now_ts),
        "evidence_path": str(evidence_info.get("evidence_path") or ""),
        "evidence_sha256": str(evidence_info.get("evidence_sha256") or ""),
        "evidence_schema": str(evidence_info.get("evidence_schema") or ""),
        "evidence_created_ts": int(evidence_info.get("evidence_created_ts") or 0),
        "reviewer": str(evidence_info.get("reviewer") or ""),
        "evidence_summary": str(evidence_info.get("evidence_summary") or "")[:200],
        "evidence_note": str(evidence_info.get("evidence_note") or "")[:200],
        "evidence_sig_ok": bool(evidence_info.get("evidence_sig_ok")),
        "evidence_sig_alg": str(evidence_info.get("evidence_sig_alg") or ""),
        "evidence_sig_key_id": str(evidence_info.get("evidence_sig_key_id") or ""),
        "evidence_sig_error_code": str(evidence_info.get("evidence_sig_error_code") or ""),
        "evidence_payload_hash": str(evidence_info.get("evidence_payload_hash") or ""),
        "l4w_envelope_path": str(l4w_info.get("l4w_envelope_path") or ""),
        "l4w_envelope_sha256": str(l4w_info.get("l4w_envelope_sha256") or ""),
        "l4w_envelope_hash": str(l4w_info.get("l4w_envelope_hash") or ""),
        "l4w_prev_hash": str(l4w_info.get("l4w_prev_hash") or ""),
        "l4w_pub_fingerprint": str(l4w_info.get("l4w_pub_fingerprint") or ""),
    }
    if warnings:
        clear_details["warnings"] = list(warnings)

    _append_event(
        _set_event_row(
            event_type="QUARANTINE_CLEAR",
            agent_id=aid,
            event_id=current_eid,
            severity=str(row.get("severity") or ""),
            reason_code=str(row.get("reason_code") or ""),
            step="drift.quarantine.clear",
            details=clear_details,
        )
    )
    _note_success()

    out = {
        "ok": True,
        "cleared": True,
        "agent_id": aid,
        "event_id": current_eid,
        "prev_active": prev_active,
        "now_active": False,
        "on_time": bool(on_time),
        "late": bool(late),
        "deadline_ts": int(deadline_ts),
        "cleared_ts": int(now_ts),
        "evidence_path": str(evidence_info.get("evidence_path") or ""),
        "evidence_sha256": str(evidence_info.get("evidence_sha256") or ""),
        "evidence_schema": str(evidence_info.get("evidence_schema") or ""),
        "evidence_created_ts": int(evidence_info.get("evidence_created_ts") or 0),
        "reviewer": str(evidence_info.get("reviewer") or ""),
        "evidence_summary": str(evidence_info.get("evidence_summary") or "")[:200],
        "evidence_note": str(evidence_info.get("evidence_note") or "")[:200],
        "evidence_sig_ok": bool(evidence_info.get("evidence_sig_ok")),
        "evidence_sig_alg": str(evidence_info.get("evidence_sig_alg") or ""),
        "evidence_sig_key_id": str(evidence_info.get("evidence_sig_key_id") or ""),
        "evidence_sig_error_code": str(evidence_info.get("evidence_sig_error_code") or ""),
        "evidence_payload_hash": str(evidence_info.get("evidence_payload_hash") or ""),
        "l4w_envelope_path": str(l4w_info.get("l4w_envelope_path") or ""),
        "l4w_envelope_sha256": str(l4w_info.get("l4w_envelope_sha256") or ""),
        "l4w_envelope_hash": str(l4w_info.get("l4w_envelope_hash") or ""),
        "l4w_prev_hash": str(l4w_info.get("l4w_prev_hash") or ""),
        "l4w_pub_fingerprint": str(l4w_info.get("l4w_pub_fingerprint") or ""),
        "slot": eff_slot,
        "enforced": bool(enforced),
        "degraded": bool(eff_slot != raw_slot),
        "mode_forced": str(_failure_snapshot(fail_max).get("mode_forced") or ""),
    }
    if warnings:
        out["warnings"] = list(warnings)
    return out


def set_manual_quarantine(
    agent_id: str,
    *,
    reason_code: str,
    severity: str = "HIGH",
    kind: str = "integrity_tamper",
    source: str = "integrity.guard",
    template_id: str = "",
    computed_hash: str = "",
    stored_hash: str = "",
    added: List[str] | None = None,
    removed: List[str] | None = None,
    challenge_sec: int | None = None,
    details: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    rcode = str(reason_code or "").strip()
    sev = str(severity or "HIGH").strip().upper() or "HIGH"
    knd = str(kind or "integrity_tamper").strip() or "integrity_tamper"
    if not aid:
        return {"ok": False, "error": "agent_id_required", "error_code": "AGENT_ID_REQUIRED"}
    if not rcode:
        return {"ok": False, "error": "reason_code_required", "error_code": "REASON_CODE_REQUIRED"}

    fail_max = _fail_max()
    fail_state = _failure_snapshot(fail_max)
    raw_slot = _slot()
    eff_slot = _effective_slot()
    enforced = bool(eff_slot == "B")
    try:
        state = _load_state(use_cache=False)
        current = _normalize_state_entry(aid, dict(state.get(aid) or _state_row_defaults(aid)))
        now_ts = int(time.time())
        challenge = int(challenge_sec if challenge_sec is not None else _challenge_sec())
        challenge = max(60, challenge)

        event_seed = f"{aid}|{knd}|{rcode}|{computed_hash}|{stored_hash}|{now_ts}"
        event_id = _event_id(
            aid,
            knd,
            rcode,
            str(computed_hash or hashlib.sha256(event_seed.encode("utf-8")).hexdigest()),
            str(stored_hash or hashlib.sha256((event_seed + "|stored").encode("utf-8")).hexdigest()),
        )

        next_row = _state_row_defaults(aid)
        next_row.update(
            {
                "agent_id": aid,
                "active": True,
                "since_ts": int(now_ts),
                "event_id": str(event_id),
                "kind": str(knd),
                "severity": str(sev),
                "reason_code": str(rcode),
                "template_id": str(template_id or current.get("template_id") or ""),
                "caps_hash": str(current.get("caps_hash") or ""),
                "computed_hash": str(computed_hash or current.get("computed_hash") or ""),
                "stored_hash": str(stored_hash or current.get("stored_hash") or ""),
                "added": [str(x) for x in list(added or [])[:10] if str(x).strip()],
                "removed": [str(x) for x in list(removed or [])[:10] if str(x).strip()],
                "last_seen_ts": int(now_ts),
                "challenge_open_ts": int(now_ts),
                "challenge_deadline_ts": int(now_ts + challenge),
                "challenge_sec": int(challenge),
                "expired": False,
                "expired_ts": 0,
                "expired_event_id": "",
                "cleared": dict(current.get("cleared") or _state_row_defaults(aid).get("cleared") or {}),
            }
        )

        changed = bool(
            (not bool(current.get("active")))
            or (str(current.get("event_id") or "") != str(next_row.get("event_id") or ""))
            or (str(current.get("reason_code") or "") != str(next_row.get("reason_code") or ""))
            or (str(current.get("kind") or "") != str(next_row.get("kind") or ""))
        )
        state[aid] = next_row
        _save_state(state)
        if changed:
            event_details = {
                "kind": str(next_row.get("kind") or ""),
                "template_id": str(next_row.get("template_id") or ""),
                "added": list(next_row.get("added") or []),
                "removed": list(next_row.get("removed") or []),
            }
            if details:
                event_details["details"] = dict(details or {})
            _append_event(
                _set_event_row(
                    event_type="QUARANTINE_SET",
                    agent_id=aid,
                    event_id=str(next_row.get("event_id") or ""),
                    severity=str(next_row.get("severity") or ""),
                    reason_code=str(next_row.get("reason_code") or ""),
                    step=str(source or "manual"),
                    details=event_details,
                )
            )

        _note_success()
        remaining_sec, overdue_sec = _remaining_overdue(next_row, int(time.time()))
        return {
            "ok": True,
            "active": True,
            "enforced": bool(enforced),
            "slot": eff_slot,
            "event_id": str(next_row.get("event_id") or ""),
            "reason_code": str(next_row.get("reason_code") or ""),
            "severity": str(next_row.get("severity") or ""),
            "kind": str(next_row.get("kind") or ""),
            "degraded": bool(eff_slot != raw_slot),
            "mode_forced": str(fail_state.get("mode_forced") or ""),
            "challenge_open_ts": int(next_row.get("challenge_open_ts") or 0),
            "challenge_deadline_ts": int(next_row.get("challenge_deadline_ts") or 0),
            "challenge_sec": int(next_row.get("challenge_sec") or challenge),
            "expired": False,
            "expired_ts": 0,
            "expired_event_id": "",
            "challenge_remaining_sec": int(remaining_sec),
            "overdue_sec": int(overdue_sec),
            "details": {
                "template_id": str(next_row.get("template_id") or ""),
                "added": list(next_row.get("added") or []),
                "removed": list(next_row.get("removed") or []),
            },
        }
    except Exception as exc:
        err = f"manual_quarantine_error:{exc.__class__.__name__}"
        if raw_slot == "B":
            fail_after = _note_failure(err, fail_max)
            eff_after = _effective_slot()
            enforced_after = bool(eff_after == "B")
            return {
                "ok": False,
                "active": bool(enforced_after),
                "enforced": bool(enforced_after),
                "slot": eff_after,
                "event_id": "",
                "reason_code": ("QUARANTINE_UNAVAILABLE" if enforced_after else ""),
                "severity": ("HIGH" if enforced_after else ""),
                "kind": "QUARANTINE_SYSTEM",
                "error_code": "QUARANTINE_UNAVAILABLE",
                "error": err,
                "degraded": bool(eff_after != raw_slot),
                "mode_forced": str(fail_after.get("mode_forced") or ""),
                "last_rollback_reason": str(fail_after.get("last_rollback_reason") or ""),
            }
        return {
            "ok": False,
            "active": False,
            "enforced": False,
            "slot": eff_slot,
            "event_id": "",
            "reason_code": "",
            "severity": "",
            "kind": "",
            "error_code": "QUARANTINE_UNAVAILABLE",
            "error": err,
            "degraded": False,
            "mode_forced": str(fail_state.get("mode_forced") or ""),
            "last_rollback_reason": str(fail_state.get("last_rollback_reason") or ""),
        }


def note_quarantine_block(
    agent_id: str,
    event_id: str,
    reason_code: str,
    severity: str,
    *,
    step: str,
    details: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return {"ok": False, "error": "agent_id_required", "error_code": "AGENT_ID_REQUIRED"}
    row = _set_event_row(
        event_type="QUARANTINE_BLOCK",
        agent_id=aid,
        event_id=str(event_id or ""),
        severity=str(severity or "HIGH"),
        reason_code=str(reason_code or "DRIFT_QUARANTINED"),
        step=str(step or ""),
        details=dict(details or {}),
    )
    _append_event(row)
    return {"ok": True, "event": row}


def refresh_quarantine_from_drift(*, max_agents: int) -> Dict[str, Any]:
    limit = max(1, int(max_agents or _max_agents_scan_default()))
    rep = agent_factory.list_agents()
    rows = [dict(x) for x in list(rep.get("agents") or []) if isinstance(x, dict)]
    rows.sort(key=lambda x: str(x.get("agent_id") or ""))
    rows_scan = rows[:limit]

    active = 0
    failed = 0
    for row in rows_scan:
        aid = str(row.get("agent_id") or "").strip()
        if not aid:
            continue
        q = ensure_quarantine_for_agent(aid, source="refresh")
        if bool(q.get("active")):
            active += 1
        if not bool(q.get("ok")):
            failed += 1
    return {
        "ok": True,
        "slot": _effective_slot(),
        "scanned_agents": len(rows_scan),
        "scan_limited": len(rows) > limit,
        "active": int(active),
        "failed": int(failed),
    }


def _build_last_event(src: Dict[str, Any] | None) -> Dict[str, Any]:
    row = dict(src or {})
    return {
        "ts": int(row.get("ts") or 0),
        "type": str(row.get("type") or ""),
        "agent_id": str(row.get("agent_id") or ""),
        "event_id": str(row.get("event_id") or ""),
        "reason_code": str(row.get("reason_code") or ""),
        "severity": str(row.get("severity") or ""),
        "step": str(row.get("step") or ""),
    }


def _sample_row(row: Dict[str, Any]) -> Dict[str, Any]:
    src = _normalize_state_entry(str((row or {}).get("agent_id") or ""), dict(row or {}))
    now_ts = int(time.time())
    remaining_sec, overdue_sec = _remaining_overdue(src, now_ts)
    return {
        "agent_id": str(src.get("agent_id") or ""),
        "event_id": str(src.get("event_id") or ""),
        "reason_code": str(src.get("reason_code") or ""),
        "severity": str(src.get("severity") or ""),
        "since_ts": int(src.get("since_ts") or 0),
        "challenge_deadline_ts": int(src.get("challenge_deadline_ts") or 0),
        "challenge_remaining_sec": int(remaining_sec),
        "expired": bool(src.get("expired")),
        "overdue_sec": int(overdue_sec),
    }


def build_drift_quarantine_status() -> Dict[str, Any]:
    global _STATUS_CACHE, _STATUS_CACHE_KEY, _STATUS_CACHE_TS_MONO

    ttl = _ttl_sec()
    fail_max = _fail_max()
    raw_slot = _slot()
    eff_slot = _effective_slot()
    cache_key = f"{eff_slot}|{fail_max}"
    now_mono = time.monotonic()

    with _LOCK:
        if (
            _STATUS_CACHE is not None
            and _STATUS_CACHE_KEY == cache_key
            and (now_mono - _STATUS_CACHE_TS_MONO) <= float(ttl)
        ):
            return _clone(dict(_STATUS_CACHE))

    started = time.perf_counter()
    fail_state = _failure_snapshot(fail_max)
    payload: Dict[str, Any] = {
        "ok": True,
        "slot": eff_slot,
        "enforced": bool(eff_slot == "B"),
        "degraded": bool(eff_slot != raw_slot),
        "error": "",
        "summary": {
            "active": 0,
            "active_open": 0,
            "active_expired": 0,
            "cleared_on_time": 0,
            "cleared_late": 0,
            "set_recent": 0,
            "block_recent": 0,
            "last_set_ts": 0,
            "last_block_ts": 0,
            "last_expired_ts": 0,
        },
        "last_event": {
            "ts": 0,
            "type": "",
            "agent_id": "",
            "event_id": "",
            "reason_code": "",
            "severity": "",
            "step": "",
        },
        "last_clear": {
            "ts": 0,
            "agent_id": "",
            "event_id": "",
            "on_time": False,
            "late": False,
            "evidence_sha256": "",
            "evidence_path": "",
            "reviewer": "",
            "evidence_sig_ok": False,
            "evidence_sig_alg": "",
            "evidence_sig_key_id": "",
            "evidence_sig_error_code": "",
            "l4w_envelope_path": "",
            "l4w_envelope_sha256": "",
            "l4w_envelope_hash": "",
            "l4w_prev_hash": "",
            "l4w_pub_fingerprint": "",
        },
        "l4w": {
            "ok": False,
            "slot": eff_slot,
            "enforced": bool(eff_slot == "B"),
            "degraded": bool(eff_slot != raw_slot),
            "chain": {
                "agents_tracked": 0,
                "total_records": 0,
                "last_envelope_ts": 0,
                "last_envelope_hash": "",
                "last_prev_hash": "",
                "last_error": "l4w_unavailable",
            },
            "last_clear_l4w": {
                "ts": 0,
                "agent_id": "",
                "quarantine_event_id": "",
                "envelope_hash": "",
                "prev_hash": "",
                "envelope_path": "",
                "envelope_sha256": "",
                "pub_fingerprint": "",
            },
        },
        "active_agents_sample": [],
        "perf": {
            "cache_ttl_sec": int(ttl),
            "build_ms": 0,
            "state_size": 0,
            "tail_lines": 0,
            "fail_streak": int(fail_state.get("fail_streak") or 0),
            "fail_max": int(fail_state.get("fail_max") or fail_max),
            "mode_forced": str(fail_state.get("mode_forced") or ""),
            "last_rollback_reason": str(fail_state.get("last_rollback_reason") or ""),
        },
    }

    try:
        state = _load_state(use_cache=True)
        active_rows: List[Dict[str, Any]] = []
        cleared_on_time = 0
        cleared_late = 0
        last_clear_ts = 0
        for aid, row in state.items():
            rec = _normalize_state_entry(str(aid or ""), dict(row or {}))
            rec["agent_id"] = str(rec.get("agent_id") or aid)
            if bool(rec.get("active")):
                active_rows.append(rec)
            elif int((dict(rec.get("cleared") or {})).get("ts") or 0) > 0:
                cleared = dict(rec.get("cleared") or {})
                if bool(cleared.get("late")):
                    cleared_late += 1
                else:
                    cleared_on_time += 1
                cts = int(cleared.get("ts") or 0)
                if cts >= last_clear_ts:
                    last_clear_ts = cts
                    payload["last_clear"] = {
                        "ts": int(cts),
                        "agent_id": str(rec.get("agent_id") or ""),
                        "event_id": str(cleared.get("event_id") or rec.get("event_id") or ""),
                        "on_time": bool(cleared.get("on_time")),
                        "late": bool(cleared.get("late")),
                        "evidence_sha256": str(cleared.get("evidence_sha256") or ""),
                        "evidence_path": str(cleared.get("evidence_path") or ""),
                        "reviewer": str(cleared.get("reviewer") or ""),
                        "evidence_sig_ok": bool(cleared.get("evidence_sig_ok")),
                        "evidence_sig_alg": str(cleared.get("evidence_sig_alg") or ""),
                        "evidence_sig_key_id": str(cleared.get("evidence_sig_key_id") or ""),
                        "evidence_sig_error_code": str(cleared.get("evidence_sig_error_code") or ""),
                        "l4w_envelope_path": str(cleared.get("l4w_envelope_path") or ""),
                        "l4w_envelope_sha256": str(cleared.get("l4w_envelope_sha256") or ""),
                        "l4w_envelope_hash": str(cleared.get("l4w_envelope_hash") or ""),
                        "l4w_prev_hash": str(cleared.get("l4w_prev_hash") or ""),
                        "l4w_pub_fingerprint": str(cleared.get("l4w_pub_fingerprint") or ""),
                    }

        # Lazy expire checks for top recent active agents only.
        for rec in sorted(active_rows, key=lambda x: int(x.get("since_ts") or 0), reverse=True)[:50]:
            try:
                maybe_mark_expired(str(rec.get("agent_id") or ""))
            except Exception:
                pass
        state = _load_state(use_cache=True)
        active_rows = []
        for aid, row in state.items():
            rec = _normalize_state_entry(str(aid or ""), dict(row or {}))
            rec["agent_id"] = str(rec.get("agent_id") or aid)
            if bool(rec.get("active")):
                active_rows.append(rec)

        active_rows.sort(key=lambda x: int(x.get("since_ts") or 0), reverse=True)
        payload["summary"]["active"] = len(active_rows)
        payload["summary"]["active_open"] = len([x for x in active_rows if not bool(x.get("expired"))])
        payload["summary"]["active_expired"] = len([x for x in active_rows if bool(x.get("expired"))])
        payload["summary"]["cleared_on_time"] = int(cleared_on_time)
        payload["summary"]["cleared_late"] = int(cleared_late)
        payload["active_agents_sample"] = [
            _sample_row(x)
            for x in active_rows[:20]
        ]
        payload["perf"]["state_size"] = len(state)

        recent_events, tail_lines = _read_events_tail(100, _expire_tail_lines())
        payload["perf"]["tail_lines"] = int(tail_lines)
        if recent_events:
            payload["last_event"] = _build_last_event(recent_events[-1])
        for row in recent_events:
            et = str(row.get("type") or "")
            ts = int(row.get("ts") or 0)
            if et == "QUARANTINE_SET":
                payload["summary"]["set_recent"] = int(payload["summary"]["set_recent"]) + 1
                if ts >= int(payload["summary"]["last_set_ts"] or 0):
                    payload["summary"]["last_set_ts"] = ts
            elif et == "QUARANTINE_BLOCK":
                payload["summary"]["block_recent"] = int(payload["summary"]["block_recent"]) + 1
                if ts >= int(payload["summary"]["last_block_ts"] or 0):
                    payload["summary"]["last_block_ts"] = ts
            elif et == "QUARANTINE_EXPIRED":
                if ts >= int(payload["summary"]["last_expired_ts"] or 0):
                    payload["summary"]["last_expired_ts"] = ts

        if l4w_witness is not None:
            last_clear = dict(payload.get("last_clear") or {})
            try:
                payload["l4w"] = l4w_witness.build_l4w_status(
                    slot=eff_slot,
                    enforced=bool(eff_slot == "B"),
                    degraded=bool(eff_slot != raw_slot),
                    last_clear_l4w={
                        "ts": int(last_clear.get("ts") or 0),
                        "agent_id": str(last_clear.get("agent_id") or ""),
                        "quarantine_event_id": str(last_clear.get("event_id") or ""),
                        "envelope_hash": str(last_clear.get("l4w_envelope_hash") or ""),
                        "prev_hash": str(last_clear.get("l4w_prev_hash") or ""),
                        "envelope_path": str(last_clear.get("l4w_envelope_path") or ""),
                        "envelope_sha256": str(last_clear.get("l4w_envelope_sha256") or ""),
                        "pub_fingerprint": str(last_clear.get("l4w_pub_fingerprint") or ""),
                    },
                )
            except Exception as exc:
                l4w_payload = dict(payload.get("l4w") or {})
                l4w_payload["ok"] = False
                l4w_payload["slot"] = eff_slot
                l4w_payload["enforced"] = bool(eff_slot == "B")
                l4w_payload["degraded"] = bool(eff_slot != raw_slot)
                chain_payload = dict(l4w_payload.get("chain") or {})
                chain_payload["last_error"] = str(exc)
                l4w_payload["chain"] = chain_payload
                payload["l4w"] = l4w_payload
        else:
            l4w_payload = dict(payload.get("l4w") or {})
            l4w_payload["slot"] = eff_slot
            l4w_payload["enforced"] = bool(eff_slot == "B")
            l4w_payload["degraded"] = bool(eff_slot != raw_slot)
            if _env_bool("ESTER_L4W_CHAIN_DISABLED", False):
                chain_payload = dict(l4w_payload.get("chain") or {})
                chain_payload["last_error"] = "chain_disabled"
                l4w_payload["chain"] = chain_payload
            payload["l4w"] = l4w_payload

        if eff_slot == "B":
            _note_success()
    except Exception as exc:
        err = f"quarantine_status_error:{exc.__class__.__name__}"
        payload["ok"] = False
        payload["degraded"] = True
        payload["error"] = err
        if raw_slot == "B":
            fail_state = _note_failure(err, fail_max)
            eff_slot = _effective_slot()
            payload["slot"] = eff_slot
            payload["enforced"] = bool(eff_slot == "B")
            payload["degraded"] = True
            payload["perf"]["mode_forced"] = str(fail_state.get("mode_forced") or "")
            payload["perf"]["last_rollback_reason"] = str(fail_state.get("last_rollback_reason") or "")

    elapsed_ms = int((time.perf_counter() - started) * 1000.0)
    fail_state = _failure_snapshot(fail_max)
    payload["perf"]["build_ms"] = max(0, elapsed_ms)
    payload["perf"]["fail_streak"] = int(fail_state.get("fail_streak") or 0)
    payload["perf"]["fail_max"] = int(fail_state.get("fail_max") or fail_max)
    payload["perf"]["mode_forced"] = str(fail_state.get("mode_forced") or "")
    payload["perf"]["last_rollback_reason"] = str(fail_state.get("last_rollback_reason") or "")

    with _LOCK:
        _STATUS_CACHE = _clone(payload)
        _STATUS_CACHE_KEY = cache_key
        _STATUS_CACHE_TS_MONO = now_mono
    return _clone(payload)


__all__ = [
    "refresh_quarantine_from_drift",
    "ensure_quarantine_for_agent",
    "verify_evidence_packet",
    "maybe_mark_expired",
    "is_quarantined",
    "clear_quarantine",
    "set_manual_quarantine",
    "note_quarantine_block",
    "build_drift_quarantine_status",
]
