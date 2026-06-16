# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Mapping

from growth_engine.candidates import RISK_HIGH, RISK_LOW, RISK_MED
from growth_engine.common import err, ok

ALLOWED_LOW_RISK_PARAMS = {
    "router.local_weight",
    "router.judge_weight",
    "router.online_weight",
    "retrieval.semantic_weight",
    "retrieval.structured_weight",
    "retrieval.card_weight",
    "memory.salience_threshold",
    "reflection.cooldown_sec",
    "dream.priority_bias",
    "conflict.defocus_threshold",
    "answer.max_context_items",
    "tool.timeout_soft_sec",
}

BLOCKED_PARAM_PREFIXES = (
    "identity.",
    "will.",
    "persona.core.",
    "safety.",
    "witness.",
    "l4.",
    "auth.",
    "secrets.",
    "env.",
    "code.",
    "memory.authoritative_write.",
    "replication.apply.",
    "network.allow.",
    "codex.auto_execute.",
)

RISK_ALLOWED_FOR_AUTO_PROMOTION = {RISK_LOW}


def is_blocked_param(name: str) -> bool:
    clean = str(name or "").strip()
    return any(clean.startswith(prefix) for prefix in BLOCKED_PARAM_PREFIXES)


def validate_param_change(name: str, value: Any) -> dict[str, Any]:
    clean = str(name or "").strip()
    if not clean:
        return err("SRLM_PARAM_EMPTY", "empty parameter name")
    if is_blocked_param(clean):
        return err("SRLM_PARAM_BLOCKED", f"blocked parameter: {clean}", param=clean)
    if clean not in ALLOWED_LOW_RISK_PARAMS:
        return err("SRLM_PARAM_NOT_ALLOWLISTED", f"parameter is not allowlisted: {clean}", param=clean)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return err("SRLM_PARAM_NON_NUMERIC", f"parameter must be numeric: {clean}", param=clean)
    return ok(param=clean, value=float(value))


def validate_params(params: Mapping[str, Any]) -> dict[str, Any]:
    clean: dict[str, float] = {}
    for key, value in dict(params or {}).items():
        rep = validate_param_change(str(key), value)
        if not rep.get("ok"):
            return rep
        clean[str(key)] = float(value)
    return ok(params=clean, risk_class=RISK_LOW)


def validate_candidate_risk(risk_class: str, *, promote_low_only: bool = True) -> dict[str, Any]:
    risk = str(risk_class or "").strip().lower()
    if risk == RISK_LOW:
        return ok(risk_class=risk)
    if risk in {RISK_MED, RISK_HIGH}:
        if promote_low_only:
            return err(
                "SRLM_HUMAN_REVIEW_REQUIRED",
                f"risk={risk} remains candidate-only until human/operator review",
                risk_class=risk,
            )
        return err(
            "SRLM_APPROVER_REQUIRED",
            f"risk={risk} requires explicit human approver",
            risk_class=risk,
        )
    return err("SRLM_RISK_UNKNOWN", f"unknown risk class: {risk}", risk_class=risk)
