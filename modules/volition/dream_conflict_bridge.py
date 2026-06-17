# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

_SENSITIVE_TOKENS = ("api_key", "apikey", "authorization", "password", "payload", "prompt", "secret", "token")
_CONTROL_META_KEYS = {
    "creates_precedent",
    "does_not_authorize_action",
    "does_not_delete_signal",
    "does_not_modify_policy",
    "does_not_suppress_review",
    "normal_gate_required",
    "review_only",
    "runtime_authorization",
}


def _safe_text(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split()).strip()
    if len(text) > limit:
        return text[:limit]
    return text


def _digest_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _stable_digest(value: Dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_signal_type(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"reflection", "reflection_signal"}:
        return "reflection_signal"
    return "hypothesis"


def _infer_source(signal_type: str, meta: Dict[str, Any]) -> str:
    raw = str(meta.get("source") or "").strip().lower()
    if raw in {"dream", "reflection"}:
        return raw
    return "reflection" if signal_type == "reflection_signal" else "dream"


def _safe_extra_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in dict(meta or {}).items():
        name = str(key or "").strip()
        low = name.lower()
        if not name or name == "source":
            continue
        if name in _CONTROL_META_KEYS:
            if isinstance(value, (bool, int, float, str)) or value is None:
                out[name] = value
            continue
        if any(tok in low for tok in _SENSITIVE_TOKENS) and not low.endswith("_digest"):
            continue
        if isinstance(value, (bool, int, float)) or value is None:
            out[name] = value
        elif isinstance(value, str):
            out[name] = _safe_text(value, 120)
    return out


def record_dream_conflict(
    *,
    signal_type: str,
    proposed_action: str,
    policy_hit: str,
    reason_code: str = "",
    summary: str = "",
    raw_text: str = "",
    severity: str = "low",
    meta: dict | None = None,
) -> dict:
    """Record dream/reflection guardrail collisions without authorizing or suppressing anything."""

    try:
        from modules.volition import conflict_ledger

        safe_meta = dict(meta or {})
        normalized_signal = _normalize_signal_type(signal_type)
        source = _infer_source(normalized_signal, safe_meta)
        action_id = _safe_text(proposed_action, 120) or "dream_signal"
        hit = _safe_text(policy_hit, 120) or "dream_guardrail"
        reason = _safe_text(reason_code, 120) or hit
        severity_value = _safe_text(severity, 20) or "low"
        if severity_value not in {"low", "medium", "high"}:
            severity_value = "low"

        raw_digest = _digest_text(raw_text)
        summary_text = _safe_text(summary, 180)
        raw_preview = _safe_text(raw_text, 180)
        if not summary_text or (raw_preview and summary_text == raw_preview):
            # Dream output is hypothesis text, not evidence or memory; persist a digest, not raw payload.
            summary_text = f"{source} {action_id} signal hit {hit}"
        summary_digest = _digest_text(summary_text)
        signal_digest = raw_digest or summary_digest
        args_digest = _stable_digest(
            {
                "source": source,
                "signal_type": normalized_signal,
                "action_id": action_id,
                "policy_hit": hit,
                "reason_code": reason,
                "signal_digest": signal_digest,
            }
        )
        metadata = _safe_extra_meta(safe_meta)
        metadata.update(
            {
                # Dream/reflection output is a weak signal; this is not attention rebalancing or permission.
                "authority": "low",
                "severity": severity_value,
                "signal_type": normalized_signal,
                "signal_digest": signal_digest,
                "summary_digest": summary_digest,
                "is_command": False,
                "is_evidence": False,
                "is_memory_fact": False,
                "normal_gate_required": True,
                "review_only": True,
            }
        )
        return conflict_ledger.record_conflict(
            source=source,
            action_id=action_id,
            policy_hit=hit,
            reason_code=reason,
            reason=reason,
            actor="ester",
            step="dream_conflict_bridge",
            intent_summary=summary_text,
            args_digest=args_digest,
            metadata=metadata,
            policy_snapshot={"would_allow": False, "would_reason_code": reason, "would_reason": reason},
        )
    except Exception as exc:
        # Ledger failures must not leak into dream/runtime control flow.
        return {
            "ok": False,
            "recorded": False,
            "error": "dream_conflict_record_failed",
            "detail": exc.__class__.__name__,
        }


def record_dream_runtime_conflict(
    *,
    proposed_action: str,
    policy_hit: str,
    reason_code: str = "",
    summary: str = "",
    raw_text: str = "",
    severity: str = "low",
    meta: dict | None = None,
) -> dict:
    # Runtime hooks stay tiny; the bridge centralizes low-authority dream semantics.
    return record_dream_conflict(
        signal_type="hypothesis",
        proposed_action=proposed_action,
        policy_hit=policy_hit,
        reason_code=reason_code,
        summary=summary,
        raw_text=raw_text,
        severity=severity,
        meta=meta,
    )


def record_oracle_disabled_signal(
    *,
    channel_name: str,
    provider: str,
    hook: str,
) -> dict:
    channel = str(channel_name or "").strip().lower()
    prov = str(provider or "").strip().lower()
    if channel not in {"dream", "reflection"} or prov in {"", "auto", "any", "local"}:
        return {"ok": True, "recorded": False, "skipped": True, "reason": "not_dream_oracle_signal"}
    return record_dream_conflict(
        signal_type=("reflection_signal" if channel == "reflection" else "hypothesis"),
        proposed_action="oracle_request",
        policy_hit="dream_oracle_disabled",
        reason_code="dream_oracle_disabled",
        summary="Dream/reflection oracle provider request forced to local provider by policy.",
        raw_text="",
        severity="low",
        meta={"hook": hook, "suppressed": True},
    )


def record_safe_chat_forced_local_signal(
    *,
    origin: str,
    provider: str,
    stage_name: str = "",
    telemetry_channel: str = "",
    reason_code: str = "oracle_only_user_reply_without_oracle",
    meta: dict | None = None,
) -> dict:
    try:
        org = str(origin or "").strip().lower()
        prov = str(provider or "").strip().lower()
        if org not in {"dream", "reflection"}:
            return {"ok": True, "recorded": False, "skipped": True, "reason": "not_explicit_dream_reflection_origin"}
        if prov in {"", "auto", "any", "local", "lmstudio"}:
            return {"ok": True, "recorded": False, "skipped": True, "reason": "not_remote_safe_chat_provider"}

        safe_reason = _safe_text(reason_code, 120) or "oracle_only_user_reply_without_oracle"
        safe_fields_digest = _stable_digest(
            {
                "origin": org,
                "provider": prov,
                "stage_name": _safe_text(stage_name, 80),
                "telemetry_channel": _safe_text(telemetry_channel, 80),
                "reason_code": safe_reason,
            }
        )
        safe_meta = dict(meta or {})
        safe_meta.update(
            {
                "hook": _safe_text(safe_meta.get("hook") or "run_ester_fixed._safe_chat.forced_local", 120),
                "runtime_authorization": False,
                "does_not_modify_policy": True,
                "does_not_authorize_action": True,
                "does_not_delete_signal": True,
                "does_not_suppress_review": True,
                "creates_precedent": False,
                "suppressed": True,
            }
        )
        return record_dream_conflict(
            signal_type=("reflection_signal" if org == "reflection" else "hypothesis"),
            proposed_action="llm.remote.call",
            policy_hit="safe_chat_forced_local",
            reason_code=safe_reason,
            summary="Dream/reflection safe_chat remote provider path forced to local by policy.",
            raw_text=safe_fields_digest,
            severity="low",
            meta=safe_meta,
        )
    except Exception as exc:
        return {
            "ok": False,
            "recorded": False,
            "error": "safe_chat_forced_local_record_failed",
            "detail": exc.__class__.__name__,
        }


__all__ = [
    "record_dream_conflict",
    "record_dream_runtime_conflict",
    "record_oracle_disabled_signal",
    "record_safe_chat_forced_local_signal",
]
