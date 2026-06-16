# -*- coding: utf-8 -*-
"""growth_engine.sandbox - held-out replay and shadow evaluation.

This is the part that makes growth simultaneously *real* and *safe*: a candidate
must beat the current behaviour on a frozen held-out set, in shadow (parallel, no
side effects), before it is even allowed to reach the promotion gate.

SEAM / honest note on off-policy evaluation:
re-scoring a *new* action against an *old* recorded label is the classic off-policy
problem - a stored outcome was the score of the old action, not the new one. In this
runnable harness `ReplaySet` therefore carries a counterfactual `scorer` (the hidden
ground truth). In production you replace it with one of:
  (a) a held-out proxy/world-model scorer, or
  (b) a canary/shadow deployment: run the candidate on a small live traffic slice and
      accrue *real* human/reality/L4 outcomes before promotion.
Either way, the candidate is never judged by the model that produced it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from .behavior import BehaviorVersion, decide
from .common import mean, ok


@dataclass(frozen=True)
class ReplaySet:
    name: str
    contexts: List[Dict[str, Any]]
    scorer: Callable[[Dict[str, Any], Any], float]

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.contexts)


def shadow_eval(
    replay: ReplaySet,
    current: BehaviorVersion,
    proposed: BehaviorVersion,
    *,
    decide_fn: Callable[[Dict[str, float], Dict[str, Any]], Any] = decide,
) -> Dict[str, Any]:
    """Run current vs proposed over the held-out set; return fitness delta.

    Pure: touches no live state, writes nothing. Higher score = better.
    """
    if len(replay) == 0:
        return ok(n=0, current_mean=0.0, candidate_mean=0.0, delta=0.0, empty=True)
    cur_scores: List[float] = []
    cand_scores: List[float] = []
    for ctx in replay.contexts:
        a_cur = decide_fn(current.params, ctx)
        a_cand = decide_fn(proposed.params, ctx)
        cur_scores.append(float(replay.scorer(ctx, a_cur)))
        cand_scores.append(float(replay.scorer(ctx, a_cand)))
    cur_mean = mean(cur_scores)
    cand_mean = mean(cand_scores)
    return ok(
        n=len(replay),
        replay=replay.name,
        current_version=current.version_id,
        candidate_version=proposed.version_id,
        current_mean=cur_mean,
        candidate_mean=cand_mean,
        delta=cand_mean - cur_mean,
    )
