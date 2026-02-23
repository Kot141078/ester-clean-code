# Ester Clean Code — v0.2.1

## Summary

This release is hygiene-only. It removes tracked generated report and patch-output artifacts and tightens ignore rules to prevent reintroduction.

## Highlights

- Removed tracked generated `*.report.*` artifacts from the repository.
- Removed tracked generated patch-output artifacts (`*_patched*`, backup/rollback outputs) under `tools/patches/`.
- Strengthened `.gitignore` with explicit report and patch-output patterns.

## Security & Privacy

Security and privacy posture is unchanged from v0.2.0. No new runtime or secret handling behavior was introduced. Runtime artifacts remain excluded from public tracking.

## Verification

- `powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .` -> PASS
- `python -m compileall ESTER` -> PASS
- `python -m compileall modules` -> PASS
- `git check-ignore -v ensure_register_entry.report.json tools\patches\demo.B2c_patched` -> PASS

## Links

- AGI v1.1: https://github.com/Kot141078/advanced-global-intelligence/releases/tag/v1.1
- ester-reality-bound: https://github.com/Kot141078/ester-reality-bound
- sovereign-entity-recursion: https://github.com/Kot141078/sovereign-entity-recursion
