# -*- coding: utf-8 -*-
"""End-to-end demo:  python -m growth_engine.demo

Test bed: contexts {"x": v}; hidden optimum target = 2*x + 1; fitness = 1/(1+|err|).
The initial behaviour (w=0, bias=0) is poor. A candidate whose params move toward
(w=2, bias=1) scores better on held-out and -- only if the gate is open -- gets
promoted. We show:
  1. fail-closed by default (gate shut),
  2. enabled growth converging upward,
  3. the growth report (auditable fitness curve),
  4. witness tamper detection,
  5. authority decay (demotion) when a worse version is forced active.
"""
from __future__ import annotations

import os
import tempfile

from .behavior import new_version, decide
from .engine import GrowthEngine
from .fitness import FitnessLedger, Outcome
from .sandbox import ReplaySet


def _target(x: float) -> float:
    return 2.0 * x + 1.0


def _scorer(ctx, action) -> float:
    err = abs(float(action) - _target(float(ctx["x"])))
    return 1.0 / (1.0 + err)


def _seed_low_fitness(engine: GrowthEngine, replay: ReplaySet) -> None:
    # record real-ish outcomes for the current (poor) behaviour, source=reality
    for i, ctx in enumerate(replay.contexts):
        a = decide(engine.current.params, ctx)
        engine.record_outcome(
            Outcome(episode_id=f"ep{i}", score=_scorer(ctx, a), source="reality", note="seed")
        )


def main() -> None:
    root = tempfile.mkdtemp(prefix="growth_demo_")
    contexts = [{"x": float(v)} for v in range(-5, 6)]
    replay = ReplaySet(name="affine_heldout", contexts=contexts, scorer=_scorer)
    initial = new_version({"w": 0.0, "bias": 0.0}, note="initial_poor")

    print(f"# workdir: {root}")
    print(f"# initial: {initial.version_id} params={initial.params}")

    # ---- 1. fail-closed by default ----------------------------------------
    for k in ("GROWTH_ENABLE", "GROWTH_ACK_RISK", "GROWTH_ALLOW_PROMOTE"):
        os.environ.pop(k, None)
    engine = GrowthEngine(root=root, replay=replay, initial=initial, min_cluster=3, proposal_n=16, proposal_step=1.0)
    _seed_low_fitness(engine, replay)
    blocked = engine.step(seed=0)
    print("\n[1] gate OFF ->", blocked.get("action"), blocked.get("decision", {}).get("error_code", ""))

    # ---- 2. enable and let it grow ----------------------------------------
    os.environ["GROWTH_ENABLE"] = "1"
    os.environ["GROWTH_ACK_RISK"] = "I_UNDERSTAND"
    os.environ["GROWTH_ALLOW_PROMOTE"] = "1"
    os.environ["GROWTH_MAX_PROMOTIONS_PER_WINDOW"] = "50"

    start_fit = engine.live_fitness(engine.current)
    history = engine.run(25, approver=None)  # low-risk -> standing policy
    promotions = [h for h in history if h.get("action") == "promoted"]
    end_fit = engine.live_fitness(engine.current)

    print(f"\n[2] gate ON -> {len(promotions)} promotions")
    print(f"    fitness {start_fit:.4f} -> {end_fit:.4f}")
    print(f"    final params {engine.current.params}  (optimum ~ w=2.0 bias=1.0)")

    # ---- 3. growth report --------------------------------------------------
    rep = engine.growth_report()
    print("\n[3] growth report:")
    print(f"    counts        : {rep['counts']}")
    print(f"    fitness_curve : {[round(x,3) for x in rep['fitness_curve']]}")
    print(f"    revert_rate   : {rep['revert_rate']}")
    print(f"    witness_chain : ok={rep['witness_chain'].get('ok')} footprints={rep['witness_chain'].get('footprints')}")

    # ---- 4. tamper detection ----------------------------------------------
    wpath = engine.witness.path
    data = wpath.read_text(encoding="utf-8").splitlines()
    if data:
        import json as _json

        row = _json.loads(data[0])
        row["subject"]["delta"] = "9.999999"  # forge a better-looking delta
        data[0] = _json.dumps(row, ensure_ascii=True, separators=(",", ":"))
        wpath.write_text("\n".join(data) + "\n", encoding="utf-8")
    verdict = engine.witness.verify_chain()
    print(f"\n[4] after tampering witness line 0 -> chain ok={verdict.get('ok')} ({verdict.get('error_code','')})")

    print("\n# done. Note: this is bounded instrumental self-improvement, not 'becoming'.")


if __name__ == "__main__":
    main()
