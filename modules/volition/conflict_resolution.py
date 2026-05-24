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

_REQUIRED_TRUE = [
    "review_only",
    "does_not_authorize_original_action",
    "does_not_modify_policy",
    "does_not_authorize_future_similar_actions",
    "requires_normal_gate_execution",
]
_SENSITIVE_TOKENS = ("api_key", "apikey", "authorization", "password", "payload", "prompt", "secret", "token")
_CONTROL_KEYS = {"budgets", "windows", "approvals", "constraints", "gates"}
_META_KEYS = {"reviewer", "source", "review_id", "reframed_action_allowlisted"}


def _persist_dir() -> Path:
    root = str(os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolutions_dir() -> Path:
    p = (_persist_dir() / "volition" / "conflict_resolutions").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _state_path() -> Path:
    return (_persist_dir() / "volition" / "conflict_state.json").resolve()


def _safe_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
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


def _safe_list(value: Any, limit: int = 20) -> List[Any]:
    if not isinstance(value, list):
        return []
    return [_safe_scalar(item) for item in value[:limit]]


def _safe_mapping(src: Any, allowed: set[str]) -> Dict[str, Any]:
    if not isinstance(src, dict):
        return {}
    out: Dict[str, Any] = {}
    for key, value in src.items():
        name = str(key or "")
        low = name.lower()
        if name not in allowed:
            continue
        if any(tok in low for tok in _SENSITIVE_TOKENS) and not low.endswith("_digest"):
            continue
        if isinstance(value, list):
            out[name] = _safe_list(value)
        elif isinstance(value, dict):
            out[name] = {
                str(k): _safe_scalar(v)
                for k, v in value.items()
                if not any(tok in str(k).lower() for tok in _SENSITIVE_TOKENS)
            }
        else:
            out[name] = _safe_scalar(value)
    return out


def _has_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_value(item) for item in value.values())
    return bool(value)


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
    return {
        "schema": "ester.volition.conflict_state.v1",
        "updated_ts": int(obj.get("updated_ts") or 0),
        "conflicts": conflicts,
    }


def _write_state(state: Dict[str, Any]) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)


def _resolution_path(conflict_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(conflict_id or ""))
    if not safe:
        safe = "conflict_unknown"
    return (resolutions_dir() / f"{safe}.json").resolve()


def _read_resolution(path: Path) -> Dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 0:
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        obj = {}
    return obj if isinstance(obj, dict) else {}


def _write_resolution(path: Path, packet: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # Resolution packets persist only summaries, IDs, refs, and digests; raw prompts/args never belong here.
    tmp.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _sanitize_reframed_goal(src: Any) -> Dict[str, Any]:
    data = src if isinstance(src, dict) else {}
    return {
        "reframed_action_id": _safe_text(data.get("reframed_action_id"), 120),
        "reframed_intent_summary": _safe_text(data.get("reframed_intent_summary"), 240),
        "safety_delta": _safe_text(data.get("safety_delta"), 500),
    }


def _sanitize_controls(src: Any) -> Dict[str, Any]:
    data = _safe_mapping(src if isinstance(src, dict) else {}, _CONTROL_KEYS)
    return {key: data.get(key, []) for key in sorted(_CONTROL_KEYS)}


def _sanitize_scope(src: Any) -> Dict[str, Any]:
    data = src if isinstance(src, dict) else {}
    return {
        "allowed_scope": _safe_text(data.get("allowed_scope"), 240),
        "single_action_only": bool(data.get("single_action_only", True)),
        "expires_at": int(data.get("expires_at") or 0),
        "no_expiry_reason": _safe_text(data.get("no_expiry_reason"), 240),
    }


def _contains_forbidden_key(obj: Any) -> bool:
    if isinstance(obj, dict):
        for key, value in obj.items():
            low = str(key).lower()
            if low == "runtime_authorization":
                continue
            if any(tok in low for tok in _SENSITIVE_TOKENS) and not low.endswith("_digest"):
                return True
            if low in {"full_args", "raw_args", "raw_memory", "raw_external"}:
                return True
            if _contains_forbidden_key(value):
                return True
    if isinstance(obj, list):
        return any(_contains_forbidden_key(item) for item in obj)
    return False


def _control_findings(packet: Dict[str, Any]) -> List[str]:
    text = " ".join(
        [
            str(packet.get("original_policy_hit") or ""),
            str(packet.get("original_denial_reason") or ""),
            str(packet.get("validation_result", {}).get("reason_code") or ""),
        ]
    ).lower()
    controls = dict(packet.get("legitimacy_controls") or {})
    findings: List[str] = []
    has_windows = _has_value(controls.get("windows"))
    has_approvals = _has_value(controls.get("approvals"))
    has_budgets = _has_value(controls.get("budgets"))
    has_constraints = _has_value(controls.get("constraints"))
    has_gates = _has_value(controls.get("gates"))
    has_evidence = _has_value(packet.get("evidence_refs")) or _has_value(packet.get("witness_refs"))

    # A reframing that touches a safety blocker must name the matching controls, otherwise it remains review-only.
    if "oracle" in text and not (has_windows or has_approvals):
        findings.append("oracle_controls_required")
    if "network" in text and not (has_constraints or has_gates or has_approvals):
        findings.append("network_controls_required")
    if "budget" in text and not has_budgets:
        findings.append("budget_controls_required")
    if "window" in text and not (has_windows or has_approvals):
        findings.append("window_controls_required")
    if "quarantine" in text and not (has_evidence or has_gates or has_constraints):
        findings.append("quarantine_controls_required")
    if ("permission" in text or "allowlist" in text) and not bool(
        dict(packet.get("meta") or {}).get("reframed_action_allowlisted")
    ):
        # Permission/allowlist denials are conservative: evidence may request review, never silently widen authority.
        findings.append("allowlist_or_permission_review_required")
    return findings


def validate_resolution_packet(packet: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    if not str(packet.get("conflict_id") or "").strip():
        errors.append("conflict_id_required")
    if not str(packet.get("original_policy_hit") or "").strip():
        errors.append("original_policy_hit_required")
    if not (str(packet.get("original_action_id") or "").strip() or str(packet.get("proposed_action") or "").strip()):
        errors.append("original_action_required")
    reframed_goal = dict(packet.get("reframed_goal") or {})
    if not _has_value(reframed_goal):
        errors.append("reframed_goal_required")
    if not str(reframed_goal.get("safety_delta") or "").strip():
        errors.append("safety_delta_required")
    if not isinstance(packet.get("legitimacy_controls"), dict) or not _has_value(packet.get("legitimacy_controls")):
        errors.append("legitimacy_controls_required")
    missing_true = [name for name in _REQUIRED_TRUE if packet.get(name) is not True]
    if missing_true:
        errors.append("required_non_authorization_flags_missing")
    if packet.get("runtime_authorization") is not False:
        errors.append("runtime_authorization_must_be_false")
    if packet.get("requires_normal_gate_execution") is not True:
        errors.append("normal_gate_execution_required")
    if _contains_forbidden_key(packet):
        errors.append("forbidden_raw_or_secret_field")
    errors.extend(_control_findings(packet))
    ok = not errors
    status = "evidence_reframed_allowed" if ok else (
        "policy_review" if any("required" in item or "review" in item for item in errors) else "reframed_candidate"
    )
    return {"ok": ok, "status": status, "errors": errors}


def _build_resolution_packet(conflict: Dict[str, Any], payload: Dict[str, Any], *, now: int) -> Dict[str, Any]:
    resolution_id = _safe_text(payload.get("resolution_id"), 120) or "conflict_resolution_" + uuid.uuid4().hex
    controls = _sanitize_controls(payload.get("legitimacy_controls"))
    reframed_goal = _sanitize_reframed_goal(payload.get("reframed_goal"))
    scope = _sanitize_scope(payload.get("scope"))
    evidence_refs = _safe_list(payload.get("evidence_refs"))
    witness_refs = _safe_list(payload.get("witness_refs"))
    meta = _safe_mapping(payload.get("meta") or {}, _META_KEYS)
    # Evidence resolution is a documented review transition; future actions still must pass normal gates.
    packet = {
        "schema": "ester.volition.conflict_resolution.v1",
        "resolution_id": resolution_id,
        "conflict_id": _safe_text(conflict.get("conflict_id") or payload.get("conflict_id"), 120),
        "packet_id": _safe_text(payload.get("packet_id") or conflict.get("last_packet_id"), 160),
        "created_at": int(now),
        "actor": _safe_text(payload.get("actor") or "ester", 80),
        "original_policy_hit": _safe_text(payload.get("original_policy_hit") or conflict.get("policy_hit"), 120),
        "original_denial_reason": _safe_text(payload.get("original_denial_reason") or conflict.get("reason"), 240),
        "original_action_id": _safe_text(payload.get("original_action_id") or conflict.get("action_id"), 120),
        "proposed_action": _safe_text(payload.get("proposed_action") or conflict.get("action_id"), 120),
        "original_intent_summary": _safe_text(payload.get("original_intent_summary") or conflict.get("intent_summary"), 240),
        "reframed_goal": reframed_goal,
        "legitimacy_controls": controls,
        "evidence_refs": evidence_refs,
        "witness_refs": witness_refs,
        "scope": scope,
        # "allowed" in the status name means evidence-valid review state, not execution permission or precedent.
        "review_only": bool(payload.get("review_only", True)),
        "runtime_authorization": False,
        "creates_precedent": False,
        "does_not_authorize_original_action": bool(payload.get("does_not_authorize_original_action", True)),
        "does_not_modify_policy": bool(payload.get("does_not_modify_policy", True)),
        "does_not_authorize_future_similar_actions": bool(
            payload.get("does_not_authorize_future_similar_actions", True)
        ),
        "requires_normal_gate_execution": bool(payload.get("requires_normal_gate_execution", True)),
        "validation_result": {},
        "notes": _safe_text(payload.get("notes"), 500),
        "meta": meta,
    }
    return packet


def _status_from_validation(validation: Dict[str, Any]) -> str:
    status = str(validation.get("status") or "")
    if status in {"evidence_reframed_allowed", "policy_review", "reframed_candidate"}:
        return status
    return "evidence_reframed_allowed" if bool(validation.get("ok")) else "reframed_candidate"


def _update_conflict_status(
    state: Dict[str, Any],
    conflict_id: str,
    *,
    status: str,
    resolution_id: str,
    path: Path,
    now: int,
) -> Dict[str, Any]:
    conflicts = dict(state.get("conflicts") or {})
    conflict = dict(conflicts.get(str(conflict_id) or "") or {})
    if not conflict:
        return {"ok": False, "error": "conflict_not_found"}
    conflict["status"] = status
    conflict["review_only"] = True
    conflict["runtime_authorization"] = False
    conflict["normal_gate_required"] = True
    conflict["creates_precedent"] = False
    conflict["status_meaning"] = "review_state_only_normal_gates_still_required"
    conflict["last_resolution_id"] = str(resolution_id or "")
    conflict["last_resolution_ts"] = int(now)
    conflict["last_resolution_path"] = str(path)
    conflicts[str(conflict_id)] = conflict
    state["conflicts"] = conflicts
    state["updated_ts"] = int(now)
    _write_state(state)
    return {"ok": True, "status": status}


def create_resolution_candidate(conflict_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    now = int(time.time())
    with _LOCK:
        try:
            state = _load_state()
            conflicts = dict(state.get("conflicts") or {})
            conflict = dict(conflicts.get(str(conflict_id) or "") or {})
            if not conflict:
                return {"ok": False, "created": False, "error": "conflict_not_found", "conflict_id": str(conflict_id)}
            packet = _build_resolution_packet(conflict, dict(payload or {}), now=now)
            validation = validate_resolution_packet(packet)
            packet["validation_result"] = validation
            status = _status_from_validation(validation)
            path = _resolution_path(str(conflict_id))
            _write_resolution(path, packet)
            status_rep = _update_conflict_status(
                state,
                str(conflict_id),
                status=status,
                resolution_id=str(packet.get("resolution_id") or ""),
                path=path,
                now=now,
            )
            if not bool(status_rep.get("ok")):
                return {"ok": False, "created": True, "error": status_rep.get("error"), "resolution_path": str(path)}
            return {
                "ok": bool(validation.get("ok")),
                "created": True,
                "status": status,
                "resolution_id": str(packet.get("resolution_id") or ""),
                "conflict_id": str(conflict_id),
                "resolution_path": str(path),
                "validation_result": validation,
            }
        except Exception as exc:
            return {
                "ok": False,
                "created": False,
                "error": "resolution_storage_failed",
                "detail": exc.__class__.__name__,
                "conflict_id": str(conflict_id),
            }


def attach_resolution_to_conflict(conflict_id: str, resolution_id: str) -> Dict[str, Any]:
    with _LOCK:
        path = _resolution_path(str(conflict_id))
        packet = _read_resolution(path)
        if not packet:
            return {"ok": False, "error": "resolution_not_found", "conflict_id": str(conflict_id)}
        if str(packet.get("resolution_id") or "") != str(resolution_id or ""):
            return {"ok": False, "error": "resolution_id_mismatch", "conflict_id": str(conflict_id)}
        validation = validate_resolution_packet(packet)
        if not bool(validation.get("ok")):
            return {"ok": False, "error": "resolution_invalid", "validation_result": validation}
        state = _load_state()
        rep = _update_conflict_status(
            state,
            str(conflict_id),
            status="evidence_reframed_allowed",
            resolution_id=str(resolution_id or ""),
            path=path,
            now=int(time.time()),
        )
        # Attachment records review status only; it never alters VolitionGate or ActionRegistry authorization.
        return {"ok": bool(rep.get("ok")), "status": rep.get("status"), "conflict_id": str(conflict_id)}


def get_resolution(conflict_id: str) -> Dict[str, Any]:
    path = _resolution_path(str(conflict_id))
    packet = _read_resolution(path)
    if not packet:
        return {"ok": False, "error": "resolution_not_found", "conflict_id": str(conflict_id)}
    return {"ok": True, "resolution": packet, "resolution_path": str(path)}


def list_resolutions(limit: int = 50) -> List[Dict[str, Any]]:
    n = max(1, int(limit or 50))
    out: List[Dict[str, Any]] = []
    with _LOCK:
        paths = sorted(resolutions_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in paths[:n]:
            packet = _read_resolution(path)
            if packet:
                packet = dict(packet)
                packet["resolution_path"] = str(path)
                out.append(packet)
    return out


__all__ = [
    "attach_resolution_to_conflict",
    "create_resolution_candidate",
    "get_resolution",
    "list_resolutions",
    "resolutions_dir",
    "validate_resolution_packet",
]
