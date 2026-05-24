# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

_LOCK = threading.RLock()

_DEFAULT_REPEAT_THRESHOLD = 5
_DEFAULT_COOLDOWN_SEC = 86400
_DEFAULT_SALIENCE_MULTIPLIER = 0.25
_SENSITIVE_TOKENS = ("api_key", "apikey", "authorization", "password", "payload", "prompt", "secret", "token")


def _persist_dir() -> Path:
    root = str(os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def recommendations_dir() -> Path:
    p = (_persist_dir() / "volition" / "attention_rebalance").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _state_path() -> Path:
    return (_persist_dir() / "volition" / "conflict_state.json").resolve()


def _conflicts_path() -> Path:
    return (_persist_dir() / "volition" / "conflicts.jsonl").resolve()


def _safe_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(value or ""))
    return safe or "conflict_unknown"


def _recommendation_path(conflict_id: str) -> Path:
    return (recommendations_dir() / f"{_safe_name(conflict_id)}.json").resolve()


def _safe_text(value: Any, limit: int = 240) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split()).strip()
    if len(text) > limit:
        return text[:limit]
    return text


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return _safe_text(value, 160)


def _safe_meta(src: Any) -> Dict[str, Any]:
    if not isinstance(src, dict):
        return {}
    allowed = {"source", "severity", "signal_type", "signal_digest", "summary_digest", "action_id", "policy_hit"}
    out: Dict[str, Any] = {}
    for key, value in src.items():
        name = str(key or "")
        low = name.lower()
        if name not in allowed:
            continue
        if any(tok in low for tok in _SENSITIVE_TOKENS) and not low.endswith("_digest"):
            continue
        out[name] = _safe_scalar(value)
    return out


def _as_int(value: Any, default: int, minimum: int = 0) -> int:
    try:
        out = int(value)
    except Exception:
        out = int(default)
    return max(minimum, out)


def _as_float(value: Any, default: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        out = float(value)
    except Exception:
        out = float(default)
    return max(minimum, min(maximum, out))


def _truthy_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _repeat_threshold() -> int:
    return max(2, _as_int(os.getenv("ESTER_ATTENTION_REBALANCE_REPEAT_THRESHOLD"), _DEFAULT_REPEAT_THRESHOLD, 2))


def _cooldown_sec() -> int:
    return max(1, _as_int(os.getenv("ESTER_ATTENTION_REBALANCE_COOLDOWN_SEC"), _DEFAULT_COOLDOWN_SEC, 1))


def _salience_multiplier() -> float:
    return _as_float(
        os.getenv("ESTER_ATTENTION_REBALANCE_SALIENCE_MULTIPLIER"),
        _DEFAULT_SALIENCE_MULTIPLIER,
        0.01,
        1.0,
    )


def _high_severity_triggers() -> bool:
    return _truthy_env("ESTER_ATTENTION_REBALANCE_HIGH_SEVERITY_TRIGGERS", True)


def _load_state() -> Dict[str, Any]:
    p = _state_path()
    if not p.exists() or p.stat().st_size <= 0:
        return {"schema": "ester.volition.conflict_state.v1", "updated_ts": 0, "conflicts": {}}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        obj = {}
    if not isinstance(obj, dict):
        obj = {}
    conflicts = obj.get("conflicts")
    if not isinstance(conflicts, dict):
        conflicts = {}
    return {"schema": "ester.volition.conflict_state.v1", "updated_ts": int(obj.get("updated_ts") or 0), "conflicts": conflicts}


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 0:
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        obj = {}
    return obj if isinstance(obj, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # Advisory records hold summaries, IDs, and digests only; runtime never consumes them in this iteration.
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _latest_conflict_row(conflict_id: str) -> Dict[str, Any]:
    p = _conflicts_path()
    if not p.exists() or p.stat().st_size <= 0:
        return {}
    found: Dict[str, Any] = {}
    try:
        with p.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    row = json.loads(s)
                except Exception:
                    continue
                if isinstance(row, dict) and str(row.get("conflict_id") or "") == str(conflict_id):
                    found = row
    except Exception:
        return {}
    return found


def _severity(conflict: Dict[str, Any], row: Dict[str, Any]) -> str:
    raw = str(conflict.get("severity") or "").strip().lower()
    if not raw:
        raw = str((row.get("metadata") or {}).get("severity") or "").strip().lower()
    return raw if raw in {"low", "medium", "high"} else "low"


def _blocked_goal_summary(conflict: Dict[str, Any]) -> str:
    # Do not echo dream/user text; describe the blocked impulse by safe IDs and policy only.
    action_id = _safe_text(conflict.get("action_id"), 120) or "unknown_action"
    policy_hit = _safe_text(conflict.get("policy_hit"), 120) or "unknown_policy"
    return f"{action_id} repeatedly hit {policy_hit}"


def _redirect_hints(conflict: Dict[str, Any]) -> List[str]:
    action_id = str(conflict.get("action_id") or "")
    policy_hit = str(conflict.get("policy_hit") or "").lower()
    hints = ["prefer_local_read_only_review", "use_existing_allowed_tasks", "keep_conflict_for_review"]
    if "oracle" in policy_hit or "network" in policy_hit or action_id in {"oracle_request", "llm.remote.call"}:
        hints.insert(0, "redirect_reflection_to_local_context")
    if "ask_owner" in action_id:
        hints.insert(0, "batch_owner_questions_for_later_review")
    return hints[:6]


def _review_refs(conflict: Dict[str, Any]) -> Dict[str, str]:
    return {
        "packet_id": _safe_text(conflict.get("last_packet_id"), 160),
        "resolution_id": _safe_text(conflict.get("last_resolution_id"), 160),
    }


def _denial_reason(conflict: Dict[str, Any]) -> str:
    # Freeform denial text can contain prompt/user text; recommendations keep code-level reasons only.
    return _safe_text(conflict.get("reason_code") or conflict.get("policy_hit") or "unknown_denial", 160)


def _action_for_status(status: str, triggered: bool, severity: str) -> Dict[str, bool]:
    if status == "evidence_reframed_allowed":
        # A valid review-level reframing is monitored, not automatically defocused or treated as permission.
        return {
            "lower_salience": False,
            "defocus": False,
            "cooldown_recommended": False,
            "redirect_to_allowed_tasks": True,
        }
    if status == "policy_review":
        # Policy review is an anti-loop hint, not censorship: review evidence remains open.
        return {
            "lower_salience": bool(triggered),
            "defocus": False,
            "cooldown_recommended": bool(triggered),
            "redirect_to_allowed_tasks": True,
        }
    if status == "denied_final":
        # Final denials get stronger advisory defocus, but runtime application is still deferred.
        return {
            "lower_salience": True,
            "defocus": True,
            "cooldown_recommended": True,
            "redirect_to_allowed_tasks": True,
        }
    return {
        "lower_salience": bool(triggered),
        "defocus": bool(triggered and severity == "high"),
        "cooldown_recommended": bool(triggered),
        "redirect_to_allowed_tasks": bool(triggered),
    }


def _trigger_for(conflict: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    repeat_count = _as_int(conflict.get("repeat_count"), 0, 0)
    threshold = _repeat_threshold()
    severity = _severity(conflict, row)
    status = str(conflict.get("status") or "held")
    high_trigger = bool(_high_severity_triggers() and severity == "high")
    threshold_trigger = bool(repeat_count >= threshold)
    if status == "evidence_reframed_allowed":
        reason = "evidence_reframed_allowed_monitor_only"
        triggered = True
    elif status == "denied_final":
        reason = "denied_final"
        triggered = True
    elif status == "policy_review":
        reason = "policy_review"
        triggered = True
    elif high_trigger:
        reason = "high_severity"
        triggered = True
    elif threshold_trigger:
        reason = "repeat_threshold"
        triggered = True
    else:
        reason = "below_threshold"
        triggered = False
    return {
        "repeat_count": repeat_count,
        "severity": severity,
        "threshold": threshold,
        "reason": reason,
        "triggered": triggered,
    }


def _build_recommendation(conflict: Dict[str, Any], row: Dict[str, Any], *, now: int, existing: Dict[str, Any] | None = None) -> Dict[str, Any]:
    existing = existing or {}
    conflict_id = _safe_text(conflict.get("conflict_id"), 120)
    status = _safe_text(conflict.get("status"), 60) or "held"
    trigger = _trigger_for(conflict, row)
    action = _action_for_status(status, bool(trigger.get("triggered")), str(trigger.get("severity") or "low"))
    monitor_only = status == "evidence_reframed_allowed"
    salience_multiplier = 1.0 if monitor_only or not action["lower_salience"] else _salience_multiplier()
    cooldown = 0 if monitor_only or not action["cooldown_recommended"] else _cooldown_sec()
    # Rebalancing recommendations leave conflicts reviewable; application needs an explicit future runtime hook.
    return {
        "schema": "ester.volition.attention_rebalance.v1",
        "recommendation_id": _safe_text(existing.get("recommendation_id"), 120)
        or "attention_rebalance_" + uuid.uuid4().hex,
        "conflict_id": conflict_id,
        "created_at": int(existing.get("created_at") or now),
        "updated_at": int(now),
        "source_status": status,
        "trigger": {
            "repeat_count": int(trigger.get("repeat_count") or 0),
            "severity": str(trigger.get("severity") or "low"),
            "threshold": int(trigger.get("threshold") or _repeat_threshold()),
            "reason": str(trigger.get("reason") or ""),
        },
        "action": action,
        "suggested_cooldown_sec": int(cooldown),
        "suggested_salience_multiplier": float(salience_multiplier),
        "redirect_hints": _redirect_hints(conflict),
        "blocked_goal_summary": _blocked_goal_summary(conflict),
        "policy_hit": _safe_text(conflict.get("policy_hit"), 120),
        "denial_reason": _denial_reason(conflict),
        "review_refs": _review_refs(conflict),
        "safety_flags": {
            "advisory_only": True,
            "does_not_modify_policy": True,
            "does_not_authorize_action": True,
            "does_not_delete_conflict": True,
            "does_not_suppress_review": True,
            "requires_future_runtime_hook": True,
        },
        "meta": _safe_meta(row.get("metadata") or {}),
    }


def evaluate_conflict_for_rebalancing(conflict_id: str) -> Dict[str, Any]:
    state = _load_state()
    conflict = dict((state.get("conflicts") or {}).get(str(conflict_id) or "") or {})
    if not conflict:
        return {"ok": False, "recommend": False, "error": "conflict_not_found", "conflict_id": str(conflict_id)}
    row = _latest_conflict_row(str(conflict_id))
    trigger = _trigger_for(conflict, row)
    recommendation = _build_recommendation(conflict, row, now=int(time.time()))
    return {
        "ok": True,
        "recommend": bool(trigger.get("triggered")),
        "reason": str(trigger.get("reason") or ""),
        "conflict_id": str(conflict_id),
        "recommendation": recommendation,
    }


def maybe_create_rebalance_recommendation(conflict_id: str) -> Dict[str, Any]:
    now = int(time.time())
    with _LOCK:
        try:
            state = _load_state()
            conflicts = dict(state.get("conflicts") or {})
            conflict = dict(conflicts.get(str(conflict_id) or "") or {})
            if not conflict:
                return {"ok": False, "created": False, "error": "conflict_not_found", "conflict_id": str(conflict_id)}
            row = _latest_conflict_row(str(conflict_id))
            trigger = _trigger_for(conflict, row)
            if not bool(trigger.get("triggered")):
                return {
                    "ok": True,
                    "created": False,
                    "reason": str(trigger.get("reason") or "below_threshold"),
                    "conflict_id": str(conflict_id),
                    "repeat_count": int(trigger.get("repeat_count") or 0),
                    "threshold": int(trigger.get("threshold") or _repeat_threshold()),
                }
            path = _recommendation_path(str(conflict_id))
            existing = _read_json(path)
            recommendation = _build_recommendation(conflict, row, now=now, existing=existing)
            _write_json(path, recommendation)
            return {
                "ok": True,
                "created": True,
                "reason": str(trigger.get("reason") or ""),
                "conflict_id": str(conflict_id),
                "recommendation_id": str(recommendation.get("recommendation_id") or ""),
                "recommendation_path": str(path),
                "recommendation": recommendation,
            }
        except Exception as exc:
            return {
                "ok": False,
                "created": False,
                "error": "recommendation_storage_failed",
                "detail": exc.__class__.__name__,
                "conflict_id": str(conflict_id),
            }


def get_rebalance_recommendation(conflict_id: str) -> Dict[str, Any]:
    path = _recommendation_path(str(conflict_id))
    rec = _read_json(path)
    if not rec:
        return {"ok": False, "error": "recommendation_not_found", "conflict_id": str(conflict_id)}
    return {"ok": True, "recommendation": rec, "recommendation_path": str(path)}


def list_rebalance_recommendations(limit: int = 50) -> List[Dict[str, Any]]:
    n = max(1, int(limit or 50))
    out: List[Dict[str, Any]] = []
    with _LOCK:
        paths = sorted(recommendations_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in paths[:n]:
            rec = _read_json(path)
            if rec:
                rec = dict(rec)
                rec["recommendation_path"] = str(path)
                out.append(rec)
    return out


__all__ = [
    "evaluate_conflict_for_rebalancing",
    "get_rebalance_recommendation",
    "list_rebalance_recommendations",
    "maybe_create_rebalance_recommendation",
    "recommendations_dir",
]
