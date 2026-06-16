# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from growth_engine import Candidate, GrowthWitnessLedger, new_version, shadow_eval
from growth_engine.candidates import RISK_LOW
from growth_engine.common import err, ok, q

from .config import load_config
from .policy import validate_candidate_risk, validate_params
from .replay_store import build_replay
from .state import append_candidate, ensure_layout, load_promoted_policy


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


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _touched_params(current_params: Mapping[str, Any], proposed_params: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    current = dict(current_params or {})
    for key, value in dict(proposed_params or {}).items():
        if current.get(key) != value:
            out.append(str(key))
    return sorted(out)


def _shadow_policy_result(risk_class: str) -> dict[str, Any]:
    cfg = load_config()
    risk = validate_candidate_risk(risk_class, promote_low_only=cfg.promote_low_only)
    blocked_reasons: list[str] = []
    if cfg.shadow_only:
        blocked_reasons.append("shadow_only")
    if not cfg.promotion_gate_open:
        blocked_reasons.append("promotion_gate_closed")
    if not cfg.canary_enable:
        blocked_reasons.append("canary_disabled")
    if not risk.get("ok"):
        blocked_reasons.append(str(risk.get("error_code") or "risk_blocked"))
    return {
        "allowed": False,
        "blocked": True,
        "blocked_reasons": sorted(set(blocked_reasons)),
        "risk": risk,
        "promotion_gate_open": cfg.promotion_gate_open,
        "shadow_only": cfg.shadow_only,
        "canary_enable": cfg.canary_enable,
        "promote_low_only": cfg.promote_low_only,
    }


def _candidate_record(rep: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(rep.get("candidate") or {})
    ev = dict(rep.get("eval") or {})
    current_params = dict(rep.get("current_params") or {})
    proposed_params = dict(rep.get("proposed_params") or {})
    risk_class = str(candidate.get("risk_class") or RISK_LOW)
    policy_result = _shadow_policy_result(risk_class)
    return {
        "schema": "ester.srlm.shadow_candidate.v1",
        "created_at": _created_at(),
        "candidate_id": str(candidate.get("candidate_id") or ""),
        "base_version_id": str(candidate.get("base_version_id") or ""),
        "current_version": str(ev.get("current_version") or candidate.get("base_version_id") or ""),
        "candidate_version": str(ev.get("candidate_version") or ""),
        "risk_class": risk_class,
        "rationale": str(candidate.get("rationale") or ""),
        "replay": str(ev.get("replay") or ""),
        "n": int(ev.get("n", 0) or 0),
        "current_mean": float(ev.get("current_mean", 0.0) or 0.0),
        "candidate_mean": float(ev.get("candidate_mean", 0.0) or 0.0),
        "delta": float(ev.get("delta", 0.0) or 0.0),
        "proposed_params": proposed_params,
        "touched_params": _touched_params(current_params, proposed_params),
        "policy_result": policy_result,
        "promotion_attempted": False,
        "promotion_allowed": False,
        "shadow_only": bool(policy_result.get("shadow_only", True)),
        "auto_execute": False,
        "auto_ingest": False,
        "memory": "off",
    }


def _shadow_witness_subject(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": str(record.get("candidate_id") or ""),
        "current_version": str(record.get("current_version") or ""),
        "candidate_version": str(record.get("candidate_version") or ""),
        "replay": str(record.get("replay") or ""),
        "n": int(record.get("n", 0) or 0),
        "current_mean": q(float(record.get("current_mean", 0.0) or 0.0)),
        "candidate_mean": q(float(record.get("candidate_mean", 0.0) or 0.0)),
        "delta": q(float(record.get("delta", 0.0) or 0.0)),
        "risk_class": str(record.get("risk_class") or ""),
        "rationale": str(record.get("rationale") or ""),
        "touched_params": list(record.get("touched_params") or []),
        "promotion_attempted": False,
        "promotion_allowed": False,
        "shadow_only": bool(record.get("shadow_only", True)),
    }


def _write_shadow_report(root: str | None, record: Mapping[str, Any], witness_result: Mapping[str, Any]) -> str:
    paths = ensure_layout(root)
    path = paths["reports"] / "latest_shadow_report.md"
    lines = [
        "# SRLM shadow report",
        "",
        f"created_at: {record.get('created_at')}",
        f"candidate_id: {record.get('candidate_id')}",
        f"risk_class: {record.get('risk_class')}",
        f"replay: {record.get('replay')}",
        f"n: {record.get('n')}",
        f"current_mean: {record.get('current_mean')}",
        f"candidate_mean: {record.get('candidate_mean')}",
        f"delta: {record.get('delta')}",
        f"promotion_attempted: {record.get('promotion_attempted')}",
        f"promotion_allowed: {record.get('promotion_allowed')}",
        f"shadow_only: {record.get('shadow_only')}",
        f"auto_execute: {record.get('auto_execute')}",
        f"auto_ingest: {record.get('auto_ingest')}",
        f"memory: {record.get('memory')}",
        f"witness_ok: {witness_result.get('ok')}",
        f"witness_footprint_hash: {witness_result.get('footprint_hash', '')}",
        "",
        "touched_params:",
    ]
    lines.extend(f"- {name}" for name in record.get("touched_params") or [])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _persist_shadow_result(rep: dict[str, Any], *, root: str | None = None) -> dict[str, Any]:
    paths = ensure_layout(root)
    record = _candidate_record(rep)
    append_candidate(record, str(paths["root"]))
    witness = GrowthWitnessLedger(str(paths["root"]))
    witness_result = witness.append("shadow_eval", _shadow_witness_subject(record))
    if not witness_result.get("ok"):
        return err("SRLM_SHADOW_WITNESS_APPEND_FAILED", "could not record shadow witness", witness=witness_result)
    report_path = _write_shadow_report(str(paths["root"]), record, witness_result)
    out = dict(rep)
    out["persistence"] = {
        "root": str(paths["root"]),
        "candidate_path": str(paths["candidates"]),
        "witness_path": str(paths["witness"]),
        "report_path": report_path,
        "witness": witness_result,
    }
    return out


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
    rep = shadow_compare(current_params=current_params, proposed_params=merged, root=root)
    if not rep.get("ok"):
        return rep
    return _persist_shadow_result(rep, root=root)
