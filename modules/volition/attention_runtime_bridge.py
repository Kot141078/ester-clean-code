# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List

_MIN_MULTIPLIER = 0.05
_MAX_MULTIPLIER = 1.0
_SENSITIVE_TOKENS = ("api_key", "apikey", "authorization", "password", "payload", "prompt", "secret", "token")


def _truthy_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _enabled() -> bool:
    # Default-off keeps existing dream/reflection scheduling unchanged until Ivan opts in.
    return _truthy_env("ESTER_ATTENTION_REBALANCE_ENABLE", False)


def _dry_run() -> bool:
    # Dry-run reports the bias that would be applied, but never alters salience.
    return _truthy_env("ESTER_ATTENTION_REBALANCE_DRY_RUN", True)


def _norm(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split()).strip().lower()
    if len(text) > limit:
        text = text[:limit]
    return text


def _safe_text(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split()).strip()
    if len(text) > limit:
        text = text[:limit]
    return text


def _clamp_multiplier(value: Any) -> float:
    try:
        out = float(value)
    except Exception:
        out = 1.0
    return max(_MIN_MULTIPLIER, min(_MAX_MULTIPLIER, out))


def _digest_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _stable_digest(value: Dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _source(value: Any) -> str:
    raw = _norm(value, 40)
    if raw in {"dream", "dream_signal", "hypothesis"}:
        return "dream"
    if raw in {"reflection", "reflect", "reflection_signal"}:
        return "reflection"
    return raw or "unknown"


def _apply_flag_for(source: str) -> bool:
    if source == "dream":
        return _truthy_env("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", False)
    if source == "reflection":
        return _truthy_env("ESTER_ATTENTION_REBALANCE_APPLY_REFLECTION", False)
    return False


def _base_result(*, enabled: bool, dry_run: bool, reason: str, source: str, signal_type: str) -> Dict[str, Any]:
    return {
        "ok": True,
        "enabled": bool(enabled),
        "dry_run": bool(dry_run),
        "matched": False,
        "advisory_only": False,
        "apply_allowed": False,
        "salience_multiplier": 1.0,
        "defocus": False,
        "cooldown_recommended": False,
        "redirect_hints": [],
        "reason": reason,
        "recommendation_id": "",
        "conflict_id": "",
        # Attention rebalancing is focus control only; it can never grant runtime authority.
        "runtime_authorization": False,
        "does_not_modify_policy": True,
        "does_not_delete_signal": True,
        "does_not_suppress_review": True,
        "source": source,
        "signal_type": _safe_text(signal_type, 80),
    }


def _recommendations_root() -> Path:
    root = str(os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    return (Path(root).resolve() / "volition" / "attention_rebalance").resolve()


def _read_recommendations(limit: int = 200) -> List[Dict[str, Any]]:
    root = _recommendations_root()
    if not root.exists() or not root.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    paths = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths[: max(1, int(limit or 200))]:
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(obj, dict):
            rec = dict(obj)
            rec["recommendation_path"] = str(path)
            out.append(rec)
    return out


def _input_fingerprints(
    *,
    proposed_action: str,
    policy_hit: str,
    summary: str,
    digest: str,
    meta: Dict[str, Any],
) -> Dict[str, str]:
    action = _safe_text(proposed_action or meta.get("action_id"), 120)
    policy = _safe_text(policy_hit or meta.get("policy_hit"), 120)
    dig = _safe_text(digest or meta.get("signal_digest") or meta.get("summary_digest"), 128)
    summary_digest = _safe_text(meta.get("summary_digest"), 128) or _digest_text(summary)
    stable = _stable_digest({"action_id": action, "policy_hit": policy, "digest": dig or summary_digest})
    return {
        "action_id": action,
        "policy_hit": policy,
        "digest": dig,
        "summary_digest": summary_digest,
        "stable_digest": stable,
        "conflict_id": _safe_text(meta.get("conflict_id"), 160),
        "recommendation_id": _safe_text(meta.get("recommendation_id"), 160),
    }


def _match_reason(rec: Dict[str, Any], fp: Dict[str, str]) -> str:
    rec_meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else {}
    rec_conflict = _safe_text(rec.get("conflict_id"), 160)
    rec_id = _safe_text(rec.get("recommendation_id"), 160)
    if fp["conflict_id"] and fp["conflict_id"] == rec_conflict:
        return "conflict_id"
    if fp["recommendation_id"] and fp["recommendation_id"] == rec_id:
        return "recommendation_id"

    input_digests = {fp["digest"], fp["summary_digest"], fp["stable_digest"]}
    input_digests = {x for x in input_digests if x}
    rec_digests = {
        _safe_text(rec_meta.get("signal_digest"), 128),
        _safe_text(rec_meta.get("summary_digest"), 128),
    }
    rec_digests = {x for x in rec_digests if x}
    if input_digests and input_digests.intersection(rec_digests):
        return "digest"

    policy = _norm(fp["policy_hit"], 120)
    action = _norm(fp["action_id"], 120)
    rec_policy = _norm(rec.get("policy_hit"), 120) or _norm(rec_meta.get("policy_hit"), 120)
    blocked = _norm(rec.get("blocked_goal_summary"), 240)
    if policy and action and policy == rec_policy and action in blocked:
        return "action_policy"
    return ""


def _select_recommendation(fp: Dict[str, str]) -> Dict[str, Any]:
    for rec in _read_recommendations():
        reason = _match_reason(rec, fp)
        if reason:
            out = dict(rec)
            out["_match_reason"] = reason
            return out
    return {}


def _effective_multiplier(rec: Dict[str, Any]) -> float:
    status = _norm(rec.get("source_status"), 80)
    action = rec.get("action") if isinstance(rec.get("action"), dict) else {}
    lower = bool(action.get("lower_salience"))
    if status == "evidence_reframed_allowed" or not lower:
        return 1.0
    suggested = _clamp_multiplier(rec.get("suggested_salience_multiplier"))
    if status == "policy_review":
        return max(0.5, suggested)
    if status == "denied_final":
        return suggested
    return suggested


def get_runtime_attention_bias(
    *,
    source: str,
    signal_type: str,
    proposed_action: str = "",
    policy_hit: str = "",
    summary: str = "",
    digest: str = "",
    meta: dict | None = None,
) -> dict:
    """Return a safe salience bias for dream/reflection candidates.

    This bridge never authorizes actions, changes policy, deletes signals, or closes review.
    Runtime callers may only reduce candidate salience under explicit apply flags.
    Dream integration stays deferred until there is a clean dream candidate-score layer.
    """

    src = _source(source)
    dry = _dry_run()
    en = _enabled()
    result = _base_result(enabled=en, dry_run=dry, reason="disabled", source=src, signal_type=signal_type)
    if not en:
        return result

    safe_meta = dict(meta or {}) if isinstance(meta, dict) else {}
    fp = _input_fingerprints(
        proposed_action=proposed_action,
        policy_hit=policy_hit,
        summary=summary,
        digest=digest,
        meta=safe_meta,
    )
    rec = _select_recommendation(fp)
    if not rec:
        result["reason"] = "no_matching_recommendation"
        return result

    action = rec.get("action") if isinstance(rec.get("action"), dict) else {}
    status = _norm(rec.get("source_status"), 80)
    advisory_only = bool((rec.get("safety_flags") or {}).get("advisory_only", True))
    would_multiplier = _effective_multiplier(rec)
    would_defocus = bool(action.get("defocus") and would_multiplier < 1.0 and status != "evidence_reframed_allowed")
    would_cooldown = bool(action.get("cooldown_recommended") and would_multiplier < 1.0)
    source_apply_enabled = _apply_flag_for(src)
    apply_allowed = bool(source_apply_enabled and not dry and would_multiplier < 1.0)

    result.update(
        {
            "matched": True,
            "advisory_only": advisory_only,
            "apply_allowed": apply_allowed,
            "reason": "matched_" + _safe_text(rec.get("_match_reason"), 40),
            "recommendation_id": _safe_text(rec.get("recommendation_id"), 160),
            "conflict_id": _safe_text(rec.get("conflict_id"), 160),
            "redirect_hints": [
                _safe_text(x, 120)
                for x in list(rec.get("redirect_hints") or [])[:8]
                if _safe_text(x, 120)
            ],
            "would_apply": bool(source_apply_enabled and would_multiplier < 1.0),
            "would_salience_multiplier": float(would_multiplier),
            "would_defocus": bool(would_defocus),
            "would_cooldown_recommended": bool(would_cooldown),
        }
    )

    if not source_apply_enabled:
        result["reason"] = "apply_flag_disabled"
        return result
    if dry:
        result["reason"] = "dry_run"
        return result

    # Signals are reduced, not removed; review stays available and owner prompts/actions are unaffected.
    result["salience_multiplier"] = float(would_multiplier if apply_allowed else 1.0)
    result["defocus"] = bool(would_defocus and apply_allowed)
    result["cooldown_recommended"] = bool(would_cooldown and apply_allowed)
    if not apply_allowed:
        result["reason"] = "monitor_only"
    return result


__all__ = ["get_runtime_attention_bias"]
