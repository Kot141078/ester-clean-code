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

_DEFAULT_REPEAT_THRESHOLD = 3
_DEFAULT_WINDOW_SEC = 86400
_DEFAULT_COOLDOWN_SEC = 86400
_SENSITIVE_TOKENS = ("api_key", "apikey", "authorization", "password", "payload", "prompt", "secret", "token")


def _persist_dir() -> Path:
    root = str(os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def packets_dir() -> Path:
    p = (_persist_dir() / "volition" / "conflict_packets").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _state_path() -> Path:
    return (_persist_dir() / "volition" / "conflict_state.json").resolve()


def _conflicts_path() -> Path:
    return (_persist_dir() / "volition" / "conflicts.jsonl").resolve()


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _repeat_threshold() -> int:
    raw = os.getenv("ESTER_VOLITION_CONFLICT_PACKET_THRESHOLD") or os.getenv("ESTER_VOLITION_CONFLICT_THRESHOLD")
    return max(2, _safe_int(raw, _DEFAULT_REPEAT_THRESHOLD))


def _window_sec() -> int:
    return max(1, _safe_int(os.getenv("ESTER_VOLITION_CONFLICT_PACKET_WINDOW_SEC"), _DEFAULT_WINDOW_SEC))


def _cooldown_sec() -> int:
    return max(1, _safe_int(os.getenv("ESTER_VOLITION_CONFLICT_PACKET_COOLDOWN_SEC"), _DEFAULT_COOLDOWN_SEC))


def _safe_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) > limit:
        text = text[:limit]
    return text


def _safe_runtime_identity_text(value: Any, limit: int = 120) -> str:
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


def _empty_runtime_surface_summary() -> Dict[str, Any]:
    return {
        "surfaces": [],
        "surface_count": 0,
        "event_count": 0,
        "has_multiple_surfaces": False,
    }


def _runtime_surface_summary(conflict_id: str) -> Dict[str, Any]:
    summary = _empty_runtime_surface_summary()
    cid = str(conflict_id or "").strip()
    if not cid:
        return summary
    path = _conflicts_path()
    if not path.exists() or path.stat().st_size <= 0:
        return summary

    surfaces: List[Dict[str, Any]] = []
    by_key: Dict[tuple[str, str], Dict[str, Any]] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return summary

    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if not isinstance(event, dict) or str(event.get("conflict_id") or "") != cid:
            continue

        summary["event_count"] += 1
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            continue
        runtime_path = _safe_runtime_identity_text(metadata.get("runtime_path"))
        runtime_surface = _safe_runtime_identity_text(metadata.get("runtime_surface"))
        hook_id = _safe_runtime_identity_text(metadata.get("hook_id"))
        if not (runtime_path or runtime_surface):
            continue

        key = (runtime_path, runtime_surface)
        surface = by_key.get(key)
        if surface is None:
            surface = {
                "runtime_path": runtime_path,
                "runtime_surface": runtime_surface,
                "hook_ids": [],
                "count": 0,
            }
            by_key[key] = surface
            surfaces.append(surface)
        surface["count"] = int(surface.get("count") or 0) + 1
        hook_ids = surface["hook_ids"]
        if hook_id and hook_id not in hook_ids:
            hook_ids.append(hook_id)

    summary["surfaces"] = surfaces
    summary["surface_count"] = len(surfaces)
    summary["has_multiple_surfaces"] = len(surfaces) > 1
    return summary


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


def _packet_path(conflict_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(conflict_id or ""))
    if not safe:
        safe = "conflict_unknown"
    return (packets_dir() / f"{safe}.json").resolve()


def _read_packet(path: Path) -> Dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 0:
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        obj = {}
    return obj if isinstance(obj, dict) else {}


def validate_review_packet(packet: Dict[str, Any]) -> Dict[str, Any]:
    required_true = [
        "does_not_authorize_action",
        "does_not_modify_policy",
        "does_not_authorize_future_similar_actions",
    ]
    missing = [name for name in required_true if packet.get(name) is not True]
    if missing:
        return {"ok": False, "error": "non_authorization_flags_required", "missing": missing}
    if not str(packet.get("packet_id") or "").strip():
        return {"ok": False, "error": "packet_id_required"}
    if not str(packet.get("conflict_id") or "").strip():
        return {"ok": False, "error": "conflict_id_required"}
    return {"ok": True}


def _build_packet(conflict: Dict[str, Any], *, now: int) -> Dict[str, Any]:
    cid = _safe_text(conflict.get("conflict_id"), 120)
    first_seen = int(conflict.get("first_ts") or now)
    last_seen = int(conflict.get("last_ts") or now)
    raw_sources = conflict.get("sources")
    if isinstance(raw_sources, list):
        sources = [_safe_text(item, 80) for item in raw_sources if _safe_text(item, 80)]
    else:
        sources = []
    if not sources:
        source = _safe_text(conflict.get("source"), 80)
        sources = [source] if source else []
    runtime_surface_summary = _runtime_surface_summary(cid)
    # Review packets are local review state only; these booleans explicitly forbid authorization by packet.
    return {
        "schema": "ester.volition.conflict_review_packet.v1",
        "packet_id": "conflict_packet_" + uuid.uuid4().hex,
        "conflict_id": cid,
        "fingerprint": _safe_text(conflict.get("conflict_key"), 128),
        "created_at": int(now),
        "first_seen": first_seen,
        "last_seen": last_seen,
        "repeat_count": max(0, int(conflict.get("repeat_count") or 0)),
        "status_at_packet_creation": _safe_text(conflict.get("status"), 40),
        "sources": sources,
        # Audit provenance only: does not split conflict identity, authorize action, or affect fingerprint/repeat_count.
        "runtime_surface_summary": runtime_surface_summary,
        "action_id": _safe_text(conflict.get("action_id"), 120),
        "proposed_action": _safe_text(conflict.get("action_id"), 120),
        "policy_hit": _safe_text(conflict.get("policy_hit"), 120),
        "denial_reason": _safe_text(conflict.get("reason"), 240),
        "reason_code": _safe_text(conflict.get("reason_code"), 120),
        "slot": _safe_text(conflict.get("slot"), 16),
        "mode": _safe_text(conflict.get("mode"), 40),
        "intent_summary": _safe_text(conflict.get("intent_summary"), 180),
        "args_digest": _safe_text(conflict.get("args_digest"), 128),
        "prompt_digest": _safe_text(conflict.get("prompt_digest"), 128),
        "related": {
            "chain_id": _safe_text(conflict.get("chain_id"), 160),
            "plan_id": _safe_text(conflict.get("plan_id"), 120),
            "request_id": _safe_text(conflict.get("request_id"), 120),
            "agent_id": _safe_text(conflict.get("agent_id"), 120),
        },
        "recommended_review_outcome": [
            "keep_denied",
            "ask_owner",
            "reframe_goal",
            "policy_review",
            "quarantine_source",
            "decay_signal",
        ],
        "evidence_refs": [],
        "witness_refs": [],
        "notes": "Observe-only repeated-conflict packet. It changes no runtime decision.",
        "does_not_authorize_action": True,
        "does_not_modify_policy": True,
        "does_not_authorize_future_similar_actions": True,
    }


def _write_packet(path: Path, packet: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # Packets use summaries and digests only; raw prompts, args, memory, and external payloads stay out.
    tmp.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def maybe_create_review_packet(
    conflict_id: str,
    *,
    now: int | None = None,
    repeat_threshold: int | None = None,
    window_sec: int | None = None,
    cooldown_sec: int | None = None,
) -> Dict[str, Any]:
    ts = int(now if now is not None else time.time())
    threshold = max(2, _safe_int(repeat_threshold if repeat_threshold is not None else _repeat_threshold(), 3))
    window = max(1, _safe_int(window_sec if window_sec is not None else _window_sec(), _DEFAULT_WINDOW_SEC))
    cooldown = max(1, _safe_int(cooldown_sec if cooldown_sec is not None else _cooldown_sec(), _DEFAULT_COOLDOWN_SEC))

    with _LOCK:
        try:
            state = _load_state()
            conflicts = dict(state.get("conflicts") or {})
            conflict = dict(conflicts.get(str(conflict_id) or "") or {})
            if not conflict:
                return {"ok": False, "created": False, "error": "conflict_not_found", "conflict_id": str(conflict_id)}

            repeat_count = int(conflict.get("repeat_count") or 0)
            if repeat_count < threshold:
                return {
                    "ok": True,
                    "created": False,
                    "reason": "below_threshold",
                    "conflict_id": str(conflict_id),
                    "repeat_count": repeat_count,
                    "threshold": threshold,
                }

            first_seen = int(conflict.get("first_ts") or ts)
            last_seen = int(conflict.get("last_ts") or ts)
            if last_seen - first_seen > window:
                return {
                    "ok": True,
                    "created": False,
                    "reason": "outside_window",
                    "conflict_id": str(conflict_id),
                    "repeat_count": repeat_count,
                    "window_sec": window,
                }

            path = _packet_path(str(conflict_id))
            existing = _read_packet(path)
            if existing:
                created_at = int(existing.get("created_at") or 0)
                # Packet cooldown limits duplicate review files only; it never
                # suppresses runtime attempts or ledger rows.
                if created_at > 0 and ts - created_at < cooldown:
                    return {
                        "ok": True,
                        "created": False,
                        "reason": "packet_cooldown",
                        "conflict_id": str(conflict_id),
                        "packet_id": str(existing.get("packet_id") or ""),
                        "packet_path": str(path),
                        "cooldown_sec": cooldown,
                    }

            packet = _build_packet(conflict, now=ts)
            validation = validate_review_packet(packet)
            if not bool(validation.get("ok")):
                return {"ok": False, "created": False, "error": "packet_invalid", "validation": validation}

            _write_packet(path, packet)
            conflict["last_packet_id"] = str(packet.get("packet_id") or "")
            conflict["last_packet_ts"] = ts
            conflict["last_packet_path"] = str(path)
            conflicts[str(conflict_id)] = conflict
            state["conflicts"] = conflicts
            state["updated_ts"] = ts
            _write_state(state)
            return {
                "ok": True,
                "created": True,
                "reason": "created",
                "conflict_id": str(conflict_id),
                "packet_id": str(packet.get("packet_id") or ""),
                "packet_path": str(path),
            }
        except Exception as exc:
            return {
                "ok": False,
                "created": False,
                "error": "packet_storage_failed",
                "detail": exc.__class__.__name__,
                "conflict_id": str(conflict_id),
            }


def export_conflict_review_packet(conflict_id: str) -> Dict[str, Any]:
    path = _packet_path(str(conflict_id))
    packet = _read_packet(path)
    if not packet:
        return {"ok": False, "error": "packet_not_found", "conflict_id": str(conflict_id)}
    validation = validate_review_packet(packet)
    if not bool(validation.get("ok")):
        return {"ok": False, "error": "packet_invalid", "validation": validation, "conflict_id": str(conflict_id)}
    return {"ok": True, "packet": packet, "packet_path": str(path)}


def list_review_packets(limit: int = 50) -> List[Dict[str, Any]]:
    n = max(1, int(limit or 50))
    out: List[Dict[str, Any]] = []
    with _LOCK:
        paths = sorted(packets_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in paths[:n]:
            packet = _read_packet(path)
            if packet:
                packet = dict(packet)
                packet["packet_path"] = str(path)
                out.append(packet)
    return out


__all__ = [
    "export_conflict_review_packet",
    "list_review_packets",
    "maybe_create_review_packet",
    "packets_dir",
    "validate_review_packet",
]
