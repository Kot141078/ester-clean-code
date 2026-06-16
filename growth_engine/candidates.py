# -*- coding: utf-8 -*-
"""growth_engine.candidates - propose improvement candidates.

A Candidate is a typed, hashed proposal to change behavior params. Candidate
*generation* is deliberately pluggable: here we ship a simple, deterministic local
search so the engine runs end-to-end. In production the proposer can be an
LLM-driven or search-driven generator - but it only ever PROPOSES; nothing is
applied without passing held-out eval + the promotion gate.

Risk classes (used by the promotion gate):
- "low"  : numeric param tweaks (policy_threshold, weights) -> may use standing policy
- "med"  : prompt swaps, routing changes -> human approval recommended
- "high" : tool_code (self-written code) -> separate strict gate + human review +
           NO auto-exec. We never synthesize-and-run code in this reference engine.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from .behavior import BehaviorVersion, new_version
from .common import hash_obj, now_ts

RISK_LOW = "low"
RISK_MED = "med"
RISK_HIGH = "high"


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    base_version_id: str
    proposed: BehaviorVersion
    risk_class: str
    rationale: str
    created_at: int = 0


def _candidate_id(base_id: str, fp: str) -> str:
    return "cand_" + hash_obj({"base": base_id, "fp": fp})[:16]


def propose_param_candidates(
    current: BehaviorVersion,
    *,
    n: int = 8,
    step: float = 0.5,
    seed: int = 0,
    rationale: str = "local_search_from_low_fitness_cluster",
) -> List[Candidate]:
    """Deterministic-ish local search: perturb evolvable numeric params.

    Replaceable by any proposer(current, evidence) -> List[Candidate].
    """
    rng = random.Random(seed)
    keys = [k for k in ("w", "bias", "policy_threshold", "route_weight", "retrieval_weight") if k in current.params]
    if not keys:
        keys = ["w", "bias"]
    out: List[Candidate] = []
    for _ in range(int(n)):
        params = dict(current.params)
        for k in keys:
            params.setdefault(k, 0.0)
            params[k] = float(params[k]) + rng.uniform(-step, step)
        pv = new_version(params, parent=current, kind=current.kind, note="candidate")
        if pv.version_id == current.version_id:
            continue
        fp = pv.fingerprint()
        out.append(
            Candidate(
                candidate_id=_candidate_id(current.version_id, fp),
                base_version_id=current.version_id,
                proposed=pv,
                risk_class=RISK_LOW,
                rationale=rationale,
                created_at=now_ts(),
            )
        )
    return out


def make_tool_code_candidate(*args: Any, **kw: Any) -> Dict[str, Any]:
    """Code-synthesis candidates are NOT producible here.

    Returning a refusal object is intentional: auto-writing and running
    self-generated code is the single most dangerous path. It must go through a
    separate strict gate with a human-supplied, reviewed implementation - not this
    engine. See README -> Safety.
    """
    return {
        "ok": False,
        "error_code": "TOOL_CODE_SELF_SYNTH_FORBIDDEN",
        "error": "self-written code is not auto-generated or auto-executed in this engine",
        "risk_class": RISK_HIGH,
    }
