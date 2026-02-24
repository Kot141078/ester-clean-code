# Ester Clean Code v0.2.2

## Summary

This release introduces explicit opt-in gates for autonomy amplification pathways.
Default posture remains OFF with fail-closed behavior.

## Highlights

- Added `modules/util/feature_flags.py` with shared opt-in helper primitives.
- Gated initiative auto-task queueing in `modules/proactivity/initiative_engine.py`.
- Gated self-evo forge entrypoints in `modules/selfevo/forge.py`.
- Added operator policy docs for opt-in autonomy and self-evo controls.

## Security and Privacy

- Autonomy amplification is disabled by default.
- Enabling requires explicit risk acknowledgement and witness readiness.
- Missing prerequisites return no-op disabled status and do not enqueue/apply actions.
- No secrets handling changes were introduced.

## L4W Alignment

This release preserves identity + auditable privilege + witness trail requirements.
Budgets remain explicit and bounded, and ambiguous state degrades to fail-closed outcomes.
Veto/challenge framing is unchanged and documented in the opt-in policy.

## Verification

- `powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .` -> PASS
- `python -m compileall ESTER` -> PASS
- `python -m compileall modules` -> PASS
- InitiativeEngine behavior checks (OFF/default, missing ACK, missing budgets, full prereqs) -> PASS

## Links

- AGI v1.1: https://github.com/Kot141078/advanced-global-intelligence/releases/tag/v1.1
- ester-reality-bound: https://github.com/Kot141078/ester-reality-bound
- sovereign-entity-recursion: https://github.com/Kot141078/sovereign-entity-recursion
