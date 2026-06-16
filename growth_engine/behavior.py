# -*- coding: utf-8 -*-
"""growth_engine.behavior - what actually changes when the system "grows".

A BehaviorVersion is a typed, hashed, parameterised policy. Growth = promoting a
new BehaviorVersion whose params provably beat the current one on held-out data.

Kinds of params we allow to evolve (cheapest/safest first):
    policy_threshold, routing_weights, retrieval_weights, prompt_id.
Code-synthesis ("tool_code") is intentionally NOT auto-applied here - see
candidates.py and promotion.py: it requires a separate, strictest gate and a
human-supplied implementation, never auto-exec of model-written code.

RUNNABLE HARNESS / SEAM:
`decide(params, context)` below is a deterministic parametric policy so the whole
engine runs and is testable without an LLM. In ester-clean-code you replace
`decide` with a call into the real stack (router + models + memory) and you replace
the simulated scorer with the FitnessLedger (real human/reality/L4 outcomes).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .common import hash_obj, now_ts, q

EVOLVABLE_KEYS = ("w", "bias", "policy_threshold", "route_weight", "retrieval_weight")


@dataclass(frozen=True)
class BehaviorVersion:
    version_id: str
    params: Dict[str, float]
    parent_id: str = ""
    created_at: int = 0
    kind: str = "policy"  # policy|routing|retrieval|prompt
    note: str = ""

    def fingerprint(self) -> str:
        payload = {
            "kind": self.kind,
            "parent_id": self.parent_id,
            "params": {k: q(float(v)) for k, v in sorted(self.params.items())},
        }
        return hash_obj(payload)


def new_version(params: Dict[str, float], *, parent: BehaviorVersion | None = None,
                kind: str = "policy", note: str = "") -> BehaviorVersion:
    parent_id = parent.version_id if parent else ""
    tmp = BehaviorVersion(version_id="", params=dict(params), parent_id=parent_id, kind=kind, note=note)
    fp = tmp.fingerprint()
    return BehaviorVersion(
        version_id=f"bv_{fp[:16]}",
        params=dict(params),
        parent_id=parent_id,
        created_at=now_ts(),
        kind=kind,
        note=note,
    )


def decide(params: Dict[str, float], context: Dict[str, Any]) -> float:
    """Deterministic parametric policy (harness).

    Production: replace with the real decision/answer path. Here: a simple affine
    map of a context feature, which is enough to exercise the growth machinery.
    """
    x = float(context.get("x", 0.0))
    return float(params.get("w", 0.0)) * x + float(params.get("bias", 0.0))
