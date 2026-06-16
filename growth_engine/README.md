# growth_engine — bounded, auditable instrumental self-improvement

A runnable reference implementation of the "growth engine" we discussed, written to
mirror the idioms of `ester-clean-code` (fail-closed gates, hash-chained witness, L4
budgets) and to be wired into it through documented seams.

## What this is — and is NOT

**Is:** a closed loop that makes tools / policies / routing / memory-weights
*provably better* against an **external** fitness signal, where every change is
**witnessed, gated, and reversible**. Growth here is **measurable**: it produces an
auditable curve of held-out fitness over promotions.

**Is NOT:** consciousness, "becoming", subjecthood, life-stages/"childhood", or
open-ended self-rewriting. There is no claim that the system *matures into a subject*.
The honest unit is **bounded instrumental self-improvement**. Authority is *rented
from reality*, not accumulated from rhetoric — a promoted change is demoted the
moment it stops earning its keep on live/held-out outcomes.

> If growth cannot be instrumented like this — proposal, held-out eval, witnessed
> promotion, rollback, a rising curve — then what was built was not growth.

## The six parts (and the files)

1. **External fitness signal** — `fitness.py`
   `Outcome.source` must be one of `{human, reality, l4}`; a score the model gives
   *itself* is rejected. Turns "experience" from a labelled log into a ledger of
   *evaluated* outcomes.
2. **Candidate generation (pluggable)** — `candidates.py`
   Ships a deterministic local search; swap in any proposer. It only *proposes*.
   `make_tool_code_candidate()` deliberately **refuses**: self-written code is never
   auto-generated or auto-executed here.
3. **Sandbox / held-out replay / shadow-eval** — `sandbox.py`
   A candidate must beat current on a frozen held-out set, in shadow (no side
   effects), before it can reach the gate.
4. **Promotion gate** — `promotion.py`
   Fail-closed env gate (`GROWTH_ENABLE` + `GROWTH_ACK_RISK=I_UNDERSTAND` +
   `GROWTH_ALLOW_PROMOTE`) + intact witness chain + margin + **L4 budget** +
   **risk-class approval** (low → standing policy; med/high → human approver).
5. **Rollback + authority decay** — `promotion.py` / `engine.py`
   `rollback()`, `demote()`, and `monitor_and_demote()` revert a change whose live
   fitness decays below its parent.
6. **L4 budgets + fail-closed** — `common.py` + the gate
   Max promotions per rolling window; blast radius confined; everything degrades to
   a no-op when prerequisites are absent.

Orchestration + the growth report live in `engine.py`. Tamper-evident ledger in
`witness.py` (hash-chained JSONL, optional Ed25519, `verify_chain()`).

## Run it

```bash
python -m growth_engine.demo     # end-to-end: fail-closed -> growth -> report -> tamper
python run_tests.py              # 9 tests, no third-party deps (offline)
# or, in a normal env:  pip install pytest && pytest -q
```

Demo output (abridged): gate OFF → `GROWTH_GATE_CLOSED`; gate ON → fitness
`0.215 → 0.810`, params converging to the hidden optimum; `fitness_curve` rising;
witness chain `ok`; after corrupting one ledger line → `ok=False`.

## Wiring into ester-clean-code (seams)

- **`fitness.record_outcome`** ← fire from real signals only: human edits/ratings,
  task success/failure, L4 budget satisfaction. Nothing else mints fitness.
- **`behavior.decide`** ← replace the parametric harness with the real decision/answer
  path (router + models + memory). `BehaviorVersion.params` carries the evolvable
  knobs (routing/retrieval weights, thresholds, prompt id).
- **`sandbox.ReplaySet.scorer`** ← replace the counterfactual oracle with (a) a
  held-out proxy scorer, or (b) a canary/shadow deployment accruing *real* outcomes.
  (Off-policy caveat is documented in `sandbox.py`.)
- **`witness.GrowthWitnessLedger`** ← point at / merge with the existing
  `l4w_witness` chain so growth events live in the same audit trail; supply
  `priv_key_path` to sign.
- **Gate env vars** ← align with the existing `forge` opt-in
  (`ESTER_ENABLE_SELF_EVO` etc.) if you want one switch to govern both.

## Safety posture

- Disabled by default; multiple explicit prerequisites; fail-closed everywhere.
- Cheapest/safest params evolve under standing policy; prompts/routing need a human;
  **code-synthesis is out of scope and never auto-run** — that is the one genuinely
  dangerous path and it stays behind a human, reviewed, non-exec boundary.
- Every proposal / eval / promotion / rejection / rollback / demotion is witnessed;
  a change with no footprint does not count.

## Honest limitations

- The **fitness signal is the hard part** (reward hacking, sparsity, distribution
  shift). The machinery here is only as good as that signal.
- Held-out sets go stale; optimizing a proxy is not optimizing reality.
- This demonstrates *measurable improvement of bounded behaviour*. It is not, and
  does not attempt to be, evidence of any metaphysical "growth".
