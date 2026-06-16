# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from growth_engine import Candidate, GrowthWitnessLedger, PromotionGate, new_version
from growth_engine.common import err, ok

from .config import SRLMConfig, load_config
from .decision_adapter import shadow_compare
from .policy import validate_candidate_risk, validate_params
from .state import latest_rollback, load_promoted_policy, state_paths, write_promoted_policy, write_rollback_snapshot


@contextmanager
def _growth_env_from_srlm(cfg: SRLMConfig) -> Iterator[None]:
    mapping = {
        "GROWTH_ENABLE": "1" if cfg.enable else "0",
        "GROWTH_ACK_RISK": "I_UNDERSTAND" if cfg.ack_risk else "",
        "GROWTH_ALLOW_PROMOTE": "1" if cfg.allow_promote else "0",
        "GROWTH_MIN_MARGIN": str(cfg.min_margin),
        "GROWTH_MAX_PROMOTIONS_PER_WINDOW": str(cfg.max_promotions_per_window),
        "GROWTH_WINDOW_SECONDS": str(cfg.window_seconds),
    }
    old = {key: os.environ.get(key) for key in mapping}
    try:
        for key, value in mapping.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _candidate_from_payload(
    current_params: Mapping[str, Any],
    proposed_params: Mapping[str, Any],
    risk_class: str,
    candidate_id: str = "",
) -> tuple[Any, Any, Candidate]:
    current = new_version(dict(current_params), kind="ester_srlm_policy", note="current")
    proposed = new_version(dict(proposed_params), parent=current, kind="ester_srlm_policy", note="candidate")
    cand = Candidate(
        candidate_id=str(candidate_id or ("cand_" + proposed.fingerprint()[:16])),
        base_version_id=current.version_id,
        proposed=proposed,
        risk_class=str(risk_class or "low"),
        rationale="ester_srlm_promotion_candidate",
    )
    return current, proposed, cand


def verify_witness(*, root: str | None = None) -> dict[str, Any]:
    paths = state_paths(root)
    return GrowthWitnessLedger(str(paths["root"])).verify_chain()


def promote_candidate(payload: Mapping[str, Any] | None = None, *, root: str | None = None) -> dict[str, Any]:
    body = dict(payload or {})
    cfg = load_config()
    target_root = root or cfg.root
    if not cfg.enable:
        return err("SRLM_DISABLED", "ESTER_SRLM_ENABLE is not enabled")
    if not cfg.ack_risk:
        return err("SRLM_ACK_REQUIRED", "ESTER_SRLM_ACK_RISK=I_UNDERSTAND is required")
    if not cfg.allow_promote:
        return err("SRLM_PROMOTION_DISABLED", "ESTER_SRLM_ALLOW_PROMOTE is not enabled")
    if cfg.shadow_only:
        return err("SRLM_SHADOW_ONLY", "ESTER_SRLM_SHADOW_ONLY keeps promotion disabled")

    current_params = body.get("current_params")
    if not isinstance(current_params, dict):
        current_params = load_promoted_policy(target_root)
    proposed_params = body.get("proposed_params") or body.get("params") or body.get("changes")
    if not isinstance(proposed_params, dict):
        return err("SRLM_PROPOSED_PARAMS_REQUIRED", "proposed params are required")

    cur = validate_params(current_params)
    if not cur.get("ok"):
        return cur
    prop = validate_params(proposed_params)
    if not prop.get("ok"):
        return prop

    risk_class = str(body.get("risk_class") or (body.get("candidate") or {}).get("risk_class") or "low")
    risk = validate_candidate_risk(risk_class, promote_low_only=cfg.promote_low_only)
    if not risk.get("ok"):
        return risk

    witness = GrowthWitnessLedger(str(state_paths(target_root)["root"]))
    chain = witness.verify_chain()
    if not chain.get("ok"):
        return err("SRLM_WITNESS_INVALID", "growth witness chain is not intact", witness=chain)

    ev = body.get("eval")
    if not isinstance(ev, dict):
        shadow = shadow_compare(current_params=cur["params"], proposed_params=prop["params"], root=target_root)
        if not shadow.get("ok"):
            return shadow
        ev = dict(shadow.get("eval") or {})
    delta = float(ev.get("delta", 0.0) or 0.0)
    if delta < float(cfg.min_margin):
        return err("SRLM_MARGIN_NOT_MET", "shadow margin below configured minimum", delta=delta, min_margin=cfg.min_margin)

    current, _proposed, cand = _candidate_from_payload(
        cur["params"],
        prop["params"],
        risk_class,
        str(body.get("candidate_id") or (body.get("candidate") or {}).get("candidate_id") or ""),
    )

    rollback_path = write_rollback_snapshot(dict(cur["params"]), target_root, reason="before_srlm_promotion")
    gate = PromotionGate(
        witness,
        min_margin=cfg.min_margin,
        max_promotions_per_window=cfg.max_promotions_per_window,
        window_seconds=cfg.window_seconds,
        standing_policy_low=True,
    )
    with _growth_env_from_srlm(cfg):
        decision = gate.evaluate(current, cand, ev, approver=None)
    if not decision.get("ok"):
        return decision
    policy_path = write_promoted_policy(dict(prop["params"]), target_root)
    return ok(
        promoted_params=dict(prop["params"]),
        promoted_version=decision["promoted"].version_id,
        rollback_path=str(rollback_path),
        policy_path=str(policy_path),
        witness=verify_witness(root=target_root),
    )


def rollback(payload: Mapping[str, Any] | None = None, *, root: str | None = None) -> dict[str, Any]:
    body = dict(payload or {})
    cfg = load_config()
    target_root = root or cfg.root
    if not cfg.enable:
        return err("SRLM_DISABLED", "ESTER_SRLM_ENABLE is not enabled")
    if not cfg.ack_risk:
        return err("SRLM_ACK_REQUIRED", "ESTER_SRLM_ACK_RISK=I_UNDERSTAND is required")
    path_text = str(body.get("rollback_path") or "").strip()
    path = Path(path_text) if path_text else latest_rollback(target_root)
    if path is None or not path.exists():
        return err("SRLM_ROLLBACK_NOT_FOUND", "no rollback snapshot is available")
    obj = json.loads(path.read_text(encoding="utf-8"))
    params = obj.get("params") if isinstance(obj, dict) else None
    if not isinstance(params, dict):
        return err("SRLM_ROLLBACK_INVALID", "rollback snapshot has no params")
    valid = validate_params(params)
    if not valid.get("ok"):
        return valid
    write_promoted_policy(dict(valid["params"]), target_root)
    witness = GrowthWitnessLedger(str(state_paths(target_root)["root"]))
    wit = witness.append("rollback", {"rollback_path": str(path), "reason": str(body.get("reason") or "operator_rollback")})
    return ok(restored_params=dict(valid["params"]), rollback_path=str(path), witness=wit)
