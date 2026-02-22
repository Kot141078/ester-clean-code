# Release Checklist

## Release Identity

- Repository: `Kot141078/ester-clean-code`
- Branch: `main`
- Scope: public clean-code only (no runtime/private artifacts)

## Legal and Policy

- [ ] `LICENSE` present and AGPL-3.0-or-later.
- [ ] `NOTICE` present and trademark separation stated.
- [ ] `TRADEMARK.md` present and consistent with logo policy.
- [ ] `README.md` states "Ester is not a chatbot".

## L4/L4W Claims

- [ ] README includes `c = a + b` framing.
- [ ] README references L4 Reality Boundary.
- [ ] Explicit bridge is documented (identity + privilege + witness).
- [ ] Two hidden bridges are documented (Ashby and information theory).
- [ ] Earth paragraph exists (entropy, degradation, fail-closed consequence).

## Required Technical Checks

Run and require PASS:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .
```

```bash
python -m compileall ESTER
python -m compileall modules
```

## Ignore Policy Sanity

- [ ] Create local `.env` and `data/test.jsonl` for sanity test.
- [ ] `git status --porcelain` remains empty for those paths.
- [ ] Cleanup local test artifacts after verification.

## Push Readiness

- [ ] `git status` shows only intended changes.
- [ ] Commit message is explicit and auditable.
- [ ] Push only after all gates report PASS.
