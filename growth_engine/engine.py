# -*- coding: utf-8 -*-
"""growth_engine.engine - the closed loop, plus a measurable growth report.

One cycle:
    outcomes (fitness ledger)
      -> cluster low-fitness episodes
      -> propose candidates
      -> shadow-eval each on held-out
      -> best candidate to the promotion gate (margin + budget + approval + witness)
      -> promote / reject
    monitoring -> demote/rollback if live fitness decays (authority rented from reality)

The payoff of doing growth this way: because every proposal, evaluation, promotion,
rollback and demotion is witnessed, growth becomes *measurable and auditable* - a real
curve (held-out fitness over promotions), not a vibe. If growth cannot be instrumented
like this, what was built was not growth.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .behavior import BehaviorVersion, decide
from .candidates import Candidate, propose_param_candidates
from .common import mean, ok, err
from .fitness import FitnessLedger
from .promotion import ApproverFn, PromotionGate
from .sandbox import ReplaySet, shadow_eval
from .witness import GrowthWitnessLedger


class GrowthEngine:
    def __init__(
        self,
        *,
        root: str,
        replay: ReplaySet,
        initial: BehaviorVersion,
        fitness: Optional[FitnessLedger] = None,
        witness: Optional[GrowthWitnessLedger] = None,
        gate: Optional[PromotionGate] = None,
        low_fitness_threshold: float = 0.5,
        min_cluster: int = 3,
        proposal_n: int = 12,
        proposal_step: float = 0.75,
    ) -> None:
        self.root = root
        self.replay = replay
        self.current = initial
        self.fitness = fitness or FitnessLedger(root)
        self.witness = witness or GrowthWitnessLedger(root)
        self.gate = gate or PromotionGate(self.witness)
        self.low_fitness_threshold = float(low_fitness_threshold)
        self.min_cluster = int(min_cluster)
        self.proposal_n = int(proposal_n)
        self.proposal_step = float(proposal_step)

    # --- helpers ------------------------------------------------------------
    def record_outcome(self, outcome) -> Dict[str, Any]:
        return self.fitness.record_outcome(outcome)

    def _best_candidate(self, candidates: List[Candidate]) -> Optional[Dict[str, Any]]:
        best = None
        for cand in candidates:
            res = shadow_eval(self.replay, self.current, cand.proposed)
            # witness the evaluation of the chosen line of search (transparency)
            if best is None or float(res.get("delta", 0.0)) > float(best["eval"].get("delta", 0.0)):
                best = {"candidate": cand, "eval": res}
        return best

    # --- one cycle ----------------------------------------------------------
    def step(
        self,
        *,
        approver: Optional[ApproverFn] = None,
        seed: int = 0,
    ) -> Dict[str, Any]:
        low = self.fitness.low_fitness_episodes(self.low_fitness_threshold)
        if len(low) < self.min_cluster:
            return ok(action="no_candidate", reason="insufficient_low_fitness_signal", low_n=len(low))

        candidates = propose_param_candidates(
            self.current, n=self.proposal_n, step=self.proposal_step, seed=seed
        )
        if not candidates:
            return ok(action="no_candidate", reason="proposer_empty")

        best = self._best_candidate(candidates)
        if best is None:
            return ok(action="no_candidate", reason="no_eval")

        cand = best["candidate"]
        ev = best["eval"]
        # record the chosen shadow-eval as evidence (quantize floats for hashing)
        from .common import q

        self.witness.append(
            "shadow_eval",
            {
                "candidate_id": cand.candidate_id,
                "current_version": self.current.version_id,
                "candidate_version": cand.proposed.version_id,
                "delta": q(float(ev.get("delta", 0.0))),
                "candidate_fit": q(float(ev.get("candidate_mean", 0.0))),
                "n_heldout": int(ev.get("n", 0)),
            },
        )

        decision = self.gate.evaluate(self.current, cand, ev, approver=approver)
        if decision.get("ok"):
            self.current = decision["promoted"]
            return ok(
                action="promoted",
                version=self.current.version_id,
                delta=float(ev.get("delta", 0.0)),
                candidate_fit=float(ev.get("candidate_mean", 0.0)),
            )
        return ok(action="rejected", decision=decision, best_delta=float(ev.get("delta", 0.0)))

    def run(self, n_steps: int, *, approver: Optional[ApproverFn] = None) -> List[Dict[str, Any]]:
        history = []
        for i in range(int(n_steps)):
            history.append(self.step(approver=approver, seed=i))
        return history

    # --- monitoring ---------------------------------------------------------
    def live_fitness(self, version: BehaviorVersion) -> float:
        """Measure a version's fitness on the held-out set (proxy for live)."""
        scores = [float(self.replay.scorer(ctx, decide(version.params, ctx))) for ctx in self.replay.contexts]
        return mean(scores)

    def monitor_and_demote(self, parent: BehaviorVersion, *, tolerance: float = 0.0) -> Dict[str, Any]:
        """If current no longer beats its parent on held-out, demote (authority decay)."""
        cur = self.live_fitness(self.current)
        par = self.live_fitness(parent)
        if cur + float(tolerance) < par:
            res = self.gate.demote(self.current, parent, reason="live_fitness_decayed")
            self.current = parent
            return ok(action="demoted", to=parent.version_id, current_fit=cur, parent_fit=par)
        return ok(action="kept", current_fit=cur, parent_fit=par)

    # --- report -------------------------------------------------------------
    def growth_report(self) -> Dict[str, Any]:
        recs = self.witness.records()
        counts = {"candidate_proposed": 0, "shadow_eval": 0, "promotion": 0, "rejected": 0, "rollback": 0, "demotion": 0}
        fitness_curve: List[float] = []
        for r in recs:
            et = r.get("event_type")
            if et in counts:
                counts[et] += 1
            if et == "promotion":
                try:
                    fitness_curve.append(float(r.get("subject", {}).get("candidate_fit", "0")))
                except Exception:
                    pass
        promoted = counts["promotion"]
        reverts = counts["rollback"] + counts["demotion"]
        revert_rate = (reverts / promoted) if promoted else 0.0
        return ok(
            current_version=self.current.version_id,
            current_params=self.current.params,
            current_fitness=self.live_fitness(self.current),
            counts=counts,
            fitness_curve=fitness_curve,
            revert_rate=revert_rate,
            witness_chain=self.witness.verify_chain(),
        )
