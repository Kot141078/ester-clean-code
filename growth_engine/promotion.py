# -*- coding: utf-8 -*-
"""growth_engine.promotion - the gate that lets a candidate become active.

Nothing changes the running system except through here. The gate mirrors forge._gate()
in ester-clean-code: fail-closed, multiple explicit prerequisites, witness-backed.

A promotion must clear ALL of:
  1. env gate (GROWTH_ENABLE + GROWTH_ACK_RISK=I_UNDERSTAND + GROWTH_ALLOW_PROMOTE)
  2. an intact witness chain
  3. a held-out fitness delta >= min_margin
  4. an L4 budget (max promotions per rolling window)
  5. approval appropriate to the candidate's risk class
Every promotion / rejection / rollback / demotion is written to the witness ledger.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .behavior import BehaviorVersion
from .candidates import Candidate, RISK_LOW, RISK_MED, RISK_HIGH
from .common import (
    env_float,
    env_int,
    now_ts,
    parse_bool_env,
    q,
    require_env_exact,
    err,
    ok,
)
from .witness import GrowthWitnessLedger

ApproverFn = Callable[[Candidate, Dict[str, Any]], bool]


class PromotionGate:
    def __init__(
        self,
        witness: GrowthWitnessLedger,
        *,
        min_margin: float = 0.0,
        max_promotions_per_window: int = 3,
        window_seconds: int = 3600,
        standing_policy_low: bool = True,
    ) -> None:
        self.witness = witness
        self.min_margin = float(env_float("GROWTH_MIN_MARGIN", min_margin))
        self.max_promotions_per_window = int(
            env_int("GROWTH_MAX_PROMOTIONS_PER_WINDOW", max_promotions_per_window, min_value=0)
        )
        self.window_seconds = int(env_int("GROWTH_WINDOW_SECONDS", window_seconds, min_value=1))
        self.standing_policy_low = bool(standing_policy_low)

    # --- gate ---------------------------------------------------------------
    def _gate(self) -> Dict[str, Any]:
        missing = []
        if not parse_bool_env("GROWTH_ENABLE", False):
            missing.append("GROWTH_ENABLE")
        if not require_env_exact("GROWTH_ACK_RISK", "I_UNDERSTAND"):
            missing.append("GROWTH_ACK_RISK=I_UNDERSTAND")
        if not parse_bool_env("GROWTH_ALLOW_PROMOTE", False):
            missing.append("GROWTH_ALLOW_PROMOTE")
        chain = self.witness.verify_chain()
        if not chain.get("ok"):
            return err("WITNESS_CHAIN_INVALID", "refusing to promote on a broken witness chain", chain=chain)
        if missing:
            return err("GROWTH_GATE_CLOSED", "self-improvement disabled / not acknowledged", missing_prereqs=missing)
        return ok()

    def _promotions_in_window(self) -> int:
        cutoff = now_ts() - self.window_seconds
        n = 0
        for r in self.witness.records():
            if r.get("event_type") == "promotion" and int(r.get("ts", 0) or 0) >= cutoff:
                n += 1
        return n

    def _approve(self, candidate: Candidate, eval_result: Dict[str, Any], approver: Optional[ApproverFn]) -> Dict[str, Any]:
        risk = str(candidate.risk_class)
        if risk == RISK_LOW and self.standing_policy_low:
            return ok(approved=True, approver="standing_policy:low_risk")
        if approver is not None:
            try:
                decision = bool(approver(candidate, eval_result))
            except Exception as exc:  # fail-closed
                return err("APPROVER_RAISED", str(exc), approved=False)
            if decision:
                return ok(approved=True, approver="human")
            return err("APPROVAL_DENIED", "human approver declined", approved=False)
        # med/high with no approver -> fail closed
        return err("APPROVAL_REQUIRED", f"risk={risk} requires a human approver", approved=False)

    # --- decisions ----------------------------------------------------------
    def evaluate(
        self,
        current: BehaviorVersion,
        candidate: Candidate,
        eval_result: Dict[str, Any],
        *,
        approver: Optional[ApproverFn] = None,
    ) -> Dict[str, Any]:
        gate = self._gate()
        if not gate.get("ok"):
            return gate

        delta = float(eval_result.get("delta", 0.0))
        cur_fit = float(eval_result.get("current_mean", 0.0))
        cand_fit = float(eval_result.get("candidate_mean", 0.0))

        base_subject = {
            "candidate_id": candidate.candidate_id,
            "base_version": current.version_id,
            "proposed_version": candidate.proposed.version_id,
            "parent": candidate.proposed.parent_id,
            "risk_class": candidate.risk_class,
            "current_fit": q(cur_fit),
            "candidate_fit": q(cand_fit),
            "delta": q(delta),
            "n_heldout": int(eval_result.get("n", 0)),
        }

        if delta < self.min_margin:
            subj = dict(base_subject, reason="below_margin", min_margin=q(self.min_margin))
            self.witness.append("rejected", subj)
            return err("MARGIN_NOT_MET", f"delta {delta:.6f} < min_margin {self.min_margin:.6f}", subject=subj)

        used = self._promotions_in_window()
        if used >= self.max_promotions_per_window:
            subj = dict(base_subject, reason="budget_exhausted", used=used, budget=self.max_promotions_per_window)
            self.witness.append("rejected", subj)
            return err("L4_BUDGET_EXHAUSTED", f"{used}/{self.max_promotions_per_window} promotions in window", subject=subj)

        appr = self._approve(candidate, eval_result, approver)
        if not appr.get("ok"):
            subj = dict(base_subject, reason="approval_failed", detail=appr.get("error_code"))
            self.witness.append("rejected", subj)
            return err("APPROVAL_FAILED", str(appr.get("error")), subject=subj, approval=appr)

        subj = dict(base_subject, approver=str(appr.get("approver")))
        wit = self.witness.append("promotion", subj)
        if not wit.get("ok"):
            return err("WITNESS_APPEND_FAILED", "could not record promotion", witness=wit)
        return ok(
            promoted=candidate.proposed,
            approver=appr.get("approver"),
            delta=delta,
            footprint_hash=wit.get("footprint_hash"),
        )

    def rollback(self, to_version: BehaviorVersion, *, reason: str) -> Dict[str, Any]:
        subj = {"to_version": to_version.version_id, "reason": str(reason)}
        wit = self.witness.append("rollback", subj)
        return ok(rolled_back_to=to_version, footprint_hash=wit.get("footprint_hash"))

    def demote(self, from_version: BehaviorVersion, to_version: BehaviorVersion, *, reason: str) -> Dict[str, Any]:
        subj = {
            "from_version": from_version.version_id,
            "to_version": to_version.version_id,
            "reason": str(reason),
        }
        wit = self.witness.append("demotion", subj)
        return ok(demoted_to=to_version, footprint_hash=wit.get("footprint_hash"))
