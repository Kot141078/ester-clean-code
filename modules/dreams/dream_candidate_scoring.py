# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
from typing import Any, Dict

_MIN_SCORE = 0.05
_SENSITIVE_TOKENS = ("api_key", "apikey", "authorization", "password", "payload", "prompt", "secret", "token")


def _safe_text(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split()).strip()
    if len(text) > limit:
        text = text[:limit]
    return text


def _safe_score(value: Any) -> float:
    try:
        out = float(value)
    except Exception:
        out = 1.0
    return max(_MIN_SCORE, out)


def _digest_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _candidate_digest(candidate: Dict[str, Any], meta: Dict[str, Any]) -> str:
    explicit = (
        candidate.get("digest")
        or candidate.get("signal_digest")
        or candidate.get("summary_digest")
        or meta.get("signal_digest")
        or meta.get("summary_digest")
    )
    if explicit:
        return _safe_text(explicit, 128)
    # Raw dream text may be present in synthetic/runtime candidates; keep only a digest.
    raw = candidate.get("summary") or candidate.get("title") or candidate.get("text") or ""
    return _digest_text(raw)


def _safe_meta(candidate: Dict[str, Any], meta: Dict[str, Any], digest: str) -> Dict[str, Any]:
    allowed = {"conflict_id", "recommendation_id", "action_id", "policy_hit", "reason_code", "signal_digest", "summary_digest"}
    out: Dict[str, Any] = {}
    for src in (meta, candidate):
        for key, value in dict(src or {}).items():
            name = str(key or "")
            low = name.lower()
            if name not in allowed:
                continue
            if any(tok in low for tok in _SENSITIVE_TOKENS) and not low.endswith("_digest"):
                continue
            out[name] = _safe_text(value, 160)
    if digest:
        out.setdefault("signal_digest", digest)
    return out


def _base_result(
    *,
    source: str,
    signal_type: str,
    original_score: float,
    reason: str,
) -> Dict[str, Any]:
    return {
        "ok": True,
        "source": _safe_text(source, 80) or "dream",
        "signal_type": _safe_text(signal_type, 80) or "hypothesis",
        "original_score": float(original_score),
        "score": float(original_score),
        "multiplier": 1.0,
        "changed": False,
        "matched": False,
        "dry_run": True,
        "enabled": False,
        "apply_allowed": False,
        "reason": reason,
        "conflict_id": "",
        "recommendation_id": "",
        "runtime_authorization": False,
        "does_not_modify_policy": True,
        "does_not_delete_signal": True,
        "does_not_suppress_review": True,
    }


def score_dream_candidate(
    *,
    candidate: dict,
    base_score: float = 1.0,
    source: str = "dream",
    signal_type: str = "hypothesis",
    apply_runtime_bias: bool = False,
) -> dict:
    """Score a dream/reflection candidate without wiring it into live dream selection.

    This is a scaffold seam: future runtime code may call it after a separate audit.
    Candidates are scored, never deleted, and raw dream/prompt text is reduced to digests.
    """

    candidate = dict(candidate or {})
    meta = dict(candidate.get("meta") or {}) if isinstance(candidate.get("meta"), dict) else {}
    src = _safe_text(source or candidate.get("source") or meta.get("source") or "dream", 80) or "dream"
    sig_type = _safe_text(signal_type or candidate.get("signal_type") or meta.get("signal_type") or "hypothesis", 80)
    original = _safe_score(base_score)
    result = _base_result(source=src, signal_type=sig_type, original_score=original, reason="scaffold_no_runtime_bias")

    digest = _candidate_digest(candidate, meta)
    safe_meta = _safe_meta(candidate, meta, digest)
    proposed_action = _safe_text(
        candidate.get("proposed_action") or candidate.get("action_id") or meta.get("action_id"),
        120,
    )
    policy_hit = _safe_text(candidate.get("policy_hit") or meta.get("policy_hit"), 120)

    try:
        from modules.volition.attention_runtime_bridge import get_runtime_attention_bias

        bias = get_runtime_attention_bias(
            source=src,
            signal_type=sig_type,
            proposed_action=proposed_action,
            policy_hit=policy_hit,
            summary="",
            digest=digest,
            meta=safe_meta,
        )
    except Exception:
        result["reason"] = "attention_bridge_failed"
        return result

    multiplier = max(_MIN_SCORE, min(1.0, float(bias.get("salience_multiplier") or 1.0)))
    would_multiplier = max(_MIN_SCORE, min(1.0, float(bias.get("would_salience_multiplier") or multiplier)))
    apply_allowed = bool(apply_runtime_bias and bias.get("apply_allowed"))
    final_multiplier = multiplier if apply_allowed else 1.0
    final_score = max(_MIN_SCORE, min(original, original * final_multiplier))

    # APPLY_DREAM is required before this helper may reduce a score; no amplification is used by default.
    result.update(
        {
            "score": float(final_score),
            "multiplier": float(final_multiplier),
            "changed": bool(apply_allowed and final_score < original),
            "matched": bool(bias.get("matched")),
            "dry_run": bool(bias.get("dry_run")),
            "enabled": bool(bias.get("enabled")),
            "apply_allowed": bool(apply_allowed),
            "reason": _safe_text(bias.get("reason") or result["reason"], 120),
            "conflict_id": _safe_text(bias.get("conflict_id"), 160),
            "recommendation_id": _safe_text(bias.get("recommendation_id"), 160),
            "runtime_authorization": False,
            "does_not_modify_policy": True,
            "does_not_delete_signal": True,
            "does_not_suppress_review": True,
            "would_multiplier": float(would_multiplier),
            "would_score": float(max(_MIN_SCORE, min(original, original * would_multiplier))),
            "bridge_apply_allowed": bool(bias.get("apply_allowed")),
            "runtime_bias_requested": bool(apply_runtime_bias),
        }
    )
    return result


__all__ = ["score_dream_candidate"]
