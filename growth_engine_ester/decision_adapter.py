# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Mapping

from growth_engine import Candidate, new_version, shadow_eval
from growth_engine.candidates import RISK_LOW
from growth_engine.common import err, ok

from .policy import validate_params
from .replay_store import build_replay
from .state import load_promoted_policy


def decide_params(params: Mapping[str, float], context: Mapping[str, Any]) -> float:
    p = dict(params or {})
    c = dict(context or {})
    value = 0.0
    value += float(p.get("router.local_weight", 0.0)) * float(c.get("local_signal", 0.0))
    value += float(p.get("router.judge_weight", 0.0)) * float(c.get("judge_signal", 0.0))
    value += float(p.get("router.online_weight", 0.0)) * float(c.get("online_signal", 0.0))
    value += float(p.get("retrieval.semantic_weight", 0.0)) * float(c.get("semantic_signal", 0.0))
    value += float(p.get("retrieval.structured_weight", 0.0)) * float(c.get("structured_signal", 0.0))
    value += float(p.get("retrieval.card_weight", 0.0)) * float(c.get("card_signal", 0.0))
    value += float(p.get("memory.salience_threshold", 0.0)) * 0.1
    value += float(p.get("dream.priority_bias", 0.0)) * 0.05
    value -= float(p.get("conflict.defocus_threshold", 0.0)) * 0.05
    value += float(p.get("answer.max_context_items", 0.0)) * 0.01
    value -= float(p.get("tool.timeout_soft_sec", 0.0)) * 0.01
    value -= float(p.get("reflection.cooldown_sec", 0.0)) * 0.001
    return value


def shadow_compare(
    *,
    current_params: Mapping[str, Any],
    proposed_params: Mapping[str, Any],
    root: str | None = None,
) -> dict[str, Any]:
    cur = validate_params(current_params)
    if not cur.get("ok"):
        return cur
    prop = validate_params(proposed_params)
    if not prop.get("ok"):
        return prop
    current = new_version(dict(cur["params"]), kind="ester_srlm_policy", note="current")
    proposed = new_version(dict(prop["params"]), parent=current, kind="ester_srlm_policy", note="candidate")
    replay = build_replay(root)
    ev = shadow_eval(replay, current, proposed, decide_fn=decide_params)
    cand = Candidate(
        candidate_id="cand_" + proposed.fingerprint()[:16],
        base_version_id=current.version_id,
        proposed=proposed,
        risk_class=RISK_LOW,
        rationale="ester_srlm_shadow_replay",
    )
    return ok(
        candidate={
            "candidate_id": cand.candidate_id,
            "base_version_id": cand.base_version_id,
            "risk_class": cand.risk_class,
            "rationale": cand.rationale,
            "proposed_params": dict(prop["params"]),
        },
        eval=ev,
        current_params=dict(cur["params"]),
        proposed_params=dict(prop["params"]),
    )


def shadow_step(payload: Mapping[str, Any] | None = None, *, root: str | None = None) -> dict[str, Any]:
    body = dict(payload or {})
    current_params = body.get("current_params")
    if not isinstance(current_params, dict):
        current_params = load_promoted_policy(root)
    proposed_params = body.get("proposed_params") or body.get("params") or body.get("changes")
    if not isinstance(proposed_params, dict):
        return err("SRLM_PROPOSED_PARAMS_REQUIRED", "proposed_params/params/changes must be an object")
    merged = dict(current_params)
    merged.update(proposed_params)
    return shadow_compare(current_params=current_params, proposed_params=merged, root=root)
