# Ester Clean Code — v0.2.3

## Summary

This release polishes operator-facing autonomy docs for readability and auditability.
Behavior remains functionally unchanged from v0.2.2.

## Highlights

- Rewrote `README.md` and `docs/SELF_EVO_OPTIN.md` into strict multiline Markdown.
- Added quick enable env snippet for opt-in autonomy and self-evo.
- Added fail-closed disabled/missing-prereqs output examples.
- Added `tools/staged_doc_gate.ps1` to enforce staged line counts and no-CR policy for key docs.

## Security & Privacy

- Defaults remain OFF for autonomy amplification features.
- Fail-closed behavior remains unchanged when prerequisites are missing.
- No new secret-handling behavior introduced.

## L4W Alignment

Identity, auditable privileges, witness trail, explicit budgets, and challenge window framing remain intact.
Doc readability gates reduce policy drift risk and keep safety intent reviewable.

## Verification

- `powershell -ExecutionPolicy Bypass -File .\tools\staged_doc_gate.ps1` -> PASS
- `powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .` -> PASS (`HIGH=0`, `MEDIUM=0`)
- `python -m compileall ESTER` -> PASS
- `python -m compileall modules` -> PASS

## Links

- AGI v1.1: https://github.com/Kot141078/advanced-global-intelligence/releases/tag/v1.1
- ester-reality-bound: https://github.com/Kot141078/ester-reality-bound
- sovereign-entity-recursion: https://github.com/Kot141078/sovereign-entity-recursion
