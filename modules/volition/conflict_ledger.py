# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

_LOCK = threading.RLock()

_META_KEYS = {
    "action_id",
    "agent_id",
    "args_digest",
    "authority",
    "cooldown_active",
    "creates_precedent",
    "duplicate",
    "does_not_authorize_action",
    "does_not_delete_signal",
    "does_not_modify_policy",
    "does_not_suppress_review",
    "error",
    "error_code",
    "evidence_hash",
    "evidence_ref",
    "event_id",
    "hook",
    "hook_family",
    "hook_id",
    "is_command",
    "is_evidence",
    "is_memory_fact",
    "l4w_hash",
    "l4w_ref",
    "mode",
    "normal_gate_required",
    "oracle_window",
    "plan_hash",
    "plan_id",
    "policy_hit",
    "prompt_digest",
    "reason_code",
    "request_id",
    "review_only",
    "runtime_path",
    "runtime_authorization",
    "runtime_surface",
    "severity",
    "signal_digest",
    "signal_type",
    "slot",
    "step_index",
    "summary_digest",
    "suppressed",
    "window_id",
}
# runtime_path/hook_id identify audit hook origin only; they do not authorize action or affect fingerprinting.
_IDENTITY_META_KEYS = {
    "runtime_path",
    "hook_id",
    "runtime_surface",
    "hook_family",
}
# Audit flags describe review semantics, not runtime permission; keep this
# whitelist narrow to avoid raw payload leakage.
_BOOLEAN_META_KEYS = {
    "creates_precedent",
    "does_not_authorize_action",
    "does_not_delete_signal",
    "does_not_modify_policy",
    "does_not_suppress_review",
    "normal_gate_required",
    "review_only",
    "runtime_authorization",
}
_POLICY_KEYS = {
    "allowed_hours",
    "autonomy_paused",
    "est_energy_j",
    "est_work_ms",
    "in_allowed_hours",
    "max_actions",
    "max_work_ms",
    "needs_network",
    "network_env_allowed",
    "proactive_step",
    "window",
    "would_allow",
    "would_reason",
    "would_reason_code",
}
_SENSITIVE_TOKENS = ("api_key", "apikey", "authorization", "password", "payload", "prompt", "secret", "token")


# Conflict Ledger is review memory, not an authority layer; raw payloads stay out of persistence.
def _persist_dir() -> Path:
    root = str(os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def conflicts_path() -> Path:
    p = (_persist_dir() / "volition" / "conflicts.jsonl").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.touch()
    return p


def state_path() -> Path:
    p = (_persist_dir() / "volition" / "conflict_state.json").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _safe_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) > limit:
        text = text[:limit]
    return text


def _safe_identity_text(value: Any, limit: int = 120) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return ""
    text = "".join(ch if (ch.isprintable() and ch not in "\r\n\t") else " " for ch in str(value or ""))
    text = " ".join(text.split()).strip()
    low = text.lower()
    if not text:
        return ""
    if any(tok in low for tok in _SENSITIVE_TOKENS):
        return ""
    if "\\" in text or "/" in text or ":" in text:
        return ""
    if low.startswith("traceback") or "traceback (most recent call last)" in low or 'file "' in low:
        return ""
    if len(text) > limit:
        text = text[:limit]
    return text


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return _safe_text(value)


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "yes", "y", "on"}:
            return True
        if raw in {"0", "false", "no", "n", "off", ""}:
            return False
    return False


def _safe_mapping(src: Any, keys: set[str]) -> Dict[str, Any]:
    if not isinstance(src, dict):
        return {}
    out: Dict[str, Any] = {}
    for key, value in src.items():
        name = str(key or "")
        low = name.lower()
        if name not in keys:
            continue
        if name in _IDENTITY_META_KEYS:
            safe_identity = _safe_identity_text(value)
            if safe_identity:
                out[name] = safe_identity
            continue
        if name in _BOOLEAN_META_KEYS:
            out[name] = _safe_bool(value)
            continue
        if any(tok in low for tok in _SENSITIVE_TOKENS) and not low.endswith("_digest"):
            continue
        if isinstance(value, dict):
            nested = {
                str(k): _safe_scalar(v)
                for k, v in value.items()
                if not any(tok in str(k).lower() for tok in _SENSITIVE_TOKENS)
            }
            if nested:
                out[name] = nested
        elif isinstance(value, list):
            out[name] = [_safe_scalar(v) for v in value[:20]]
        else:
            out[name] = _safe_scalar(value)
    return out


def _digest_obj(value: Dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _threshold_value(raw: Any) -> int:
    try:
        return max(2, int(raw))
    except Exception:
        return 3


def _load_state(path: Path) -> Dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 0:
        return {"schema": "ester.volition.conflict_state.v1", "updated_ts": 0, "conflicts": {}}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        obj = {}
    if not isinstance(obj, dict):
        obj = {}
    conflicts = obj.get("conflicts")
    if not isinstance(conflicts, dict):
        conflicts = {}
    return {
        "schema": "ester.volition.conflict_state.v1",
        "updated_ts": int(obj.get("updated_ts") or 0),
        "conflicts": conflicts,
    }


def _write_state(path: Path, state: Dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def record_conflict(
    *,
    source: str,
    action_id: str,
    policy_hit: str,
    reason_code: str,
    reason: str = "",
    slot: str = "",
    actor: str = "ester",
    chain_id: str = "",
    step: str = "",
    intent_summary: str = "",
    agent_id: str = "",
    plan_id: str = "",
    step_index: Any = None,
    args_digest: str = "",
    prompt_digest: str = "",
    decision_id: str = "",
    metadata: Dict[str, Any] | None = None,
    policy_snapshot: Dict[str, Any] | None = None,
    threshold: int | None = None,
) -> Dict[str, Any]:
    now = int(time.time())
    safe_metadata = _safe_mapping(metadata or {}, _META_KEYS)
    safe_policy = _safe_mapping(policy_snapshot or {}, _POLICY_KEYS)
    try:
        step_idx = int(step_index) if step_index is not None else None
    except Exception:
        step_idx = None
    key_parts = {
        "source": _safe_text(source, 80),
        "action_id": _safe_text(action_id, 120),
        "policy_hit": _safe_text(policy_hit, 120),
        "reason_code": _safe_text(reason_code, 120),
        "agent_id": _safe_text(agent_id, 120),
        "plan_id": _safe_text(plan_id, 120),
        "step_index": step_idx,
        "args_digest": _safe_text(args_digest, 128),
        "prompt_digest": _safe_text(prompt_digest, 128),
    }
    conflict_key = _digest_obj(key_parts)
    conflict_id = "conflict_" + conflict_key[:24]
    threshold_n = _threshold_value(
        threshold if threshold is not None else os.getenv("ESTER_VOLITION_CONFLICT_THRESHOLD", "3")
    )

    with _LOCK:
        sp = state_path()
        cp = conflicts_path()
        state = _load_state(sp)
        conflicts = dict(state.get("conflicts") or {})
        prev = dict(conflicts.get(conflict_id) or {})
        repeat_count = int(prev.get("repeat_count") or 0) + 1
        status = "repeated" if repeat_count > 1 else "held"
        row = {
            "schema": "ester.volition.conflict.v1",
            "event_id": "conflict_evt_" + uuid.uuid4().hex,
            "conflict_id": conflict_id,
            "conflict_key": conflict_key,
            "ts": now,
            "status": status,
            "repeat_count": repeat_count,
            "threshold_candidate": bool(repeat_count >= threshold_n),
            "source": key_parts["source"],
            "action_id": key_parts["action_id"],
            "policy_hit": key_parts["policy_hit"],
            "reason_code": key_parts["reason_code"],
            "reason": _safe_text(reason, 240),
            "slot": _safe_text(slot, 16),
            "actor": _safe_text(actor, 80),
            "chain_id": _safe_text(chain_id, 160),
            "step": _safe_text(step, 80),
            "intent_summary": _safe_text(intent_summary, 180),
            "agent_id": key_parts["agent_id"],
            "plan_id": key_parts["plan_id"],
            "step_index": step_idx,
            "args_digest": key_parts["args_digest"],
            "prompt_digest": key_parts["prompt_digest"],
            "decision_id": _safe_text(decision_id, 120),
            "metadata": safe_metadata,
            "policy_snapshot": safe_policy,
        }
        # Repetition can create a local review packet, but it never suppresses runtime retries.
        with cp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            f.flush()
        sources = [str(x) for x in list(prev.get("sources") or []) if str(x).strip()]
        if key_parts["source"] and key_parts["source"] not in sources:
            sources.append(key_parts["source"])
        conflicts[conflict_id] = {
            "conflict_id": conflict_id,
            "conflict_key": conflict_key,
            "first_ts": int(prev.get("first_ts") or now),
            "last_ts": now,
            "status": status,
            "repeat_count": repeat_count,
            "threshold_candidate": bool(repeat_count >= threshold_n),
            "source": key_parts["source"],
            "action_id": key_parts["action_id"],
            "policy_hit": key_parts["policy_hit"],
            "reason_code": key_parts["reason_code"],
            "agent_id": key_parts["agent_id"],
            "plan_id": key_parts["plan_id"],
            "step_index": step_idx,
            "args_digest": key_parts["args_digest"],
            "prompt_digest": key_parts["prompt_digest"],
            "last_event_id": row["event_id"],
            "reason": row["reason"],
            "slot": row["slot"],
            "mode": _safe_text(safe_metadata.get("mode") or "", 40),
            "chain_id": row["chain_id"],
            "intent_summary": row["intent_summary"],
            "request_id": _safe_text(safe_metadata.get("request_id") or "", 120),
            "sources": sources,
            "last_packet_id": str(prev.get("last_packet_id") or ""),
            "last_packet_ts": int(prev.get("last_packet_ts") or 0),
            "last_packet_path": str(prev.get("last_packet_path") or ""),
        }
        state["updated_ts"] = now
        state["conflicts"] = conflicts
        _write_state(sp, state)
    if repeat_count >= threshold_n:
        try:
            from modules.volition import conflict_packets

            # Packet creation is observe-only review state; failures are reported but never reauthorize anything.
            row["review_packet"] = conflict_packets.maybe_create_review_packet(
                conflict_id,
                now=now,
                repeat_threshold=threshold_n,
            )
        except Exception as exc:
            row["review_packet"] = {
                "ok": False,
                "created": False,
                "error": "packet_create_failed",
                "detail": exc.__class__.__name__,
                "conflict_id": conflict_id,
            }
    return row


def tail(limit: int = 20) -> List[Dict[str, Any]]:
    n = max(1, int(limit or 20))
    p = conflicts_path()
    if not p.exists() or p.stat().st_size <= 0:
        return []
    lines = [line.strip() for line in p.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    out: List[Dict[str, Any]] = []
    for line in lines[-n:]:
        try:
            obj = json.loads(line)
        except Exception:
            obj = {"ok": False, "error": "invalid_jsonl"}
        if isinstance(obj, dict):
            out.append(obj)
    return out


__all__ = ["conflicts_path", "record_conflict", "state_path", "tail"]
