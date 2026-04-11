# Release Checklist

## Release Identity

- Repository: `Kot141078/ester-clean-code`
- Branch: `main`
- Scope: public clean-code only

## Legal and Policy

- [ ] `LICENSE` present and AGPL-3.0-or-later.
- [ ] `NOTICE` present and trademark boundary stated.
- [ ] `TRADEMARK.md` present and consistent with logo policy.
- [ ] README states "Ester is not a chatbot".

## L4/L4W Claims

- [ ] README includes `c = a + b`.
- [ ] README describes L4 Reality Boundary.
- [ ] README includes explicit bridge.
- [ ] README includes hidden Ashby bridge.
- [ ] README includes hidden Cover and Thomas bridge.
- [ ] README includes earth paragraph and fail-closed implication.

## Required Command Checks

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .
```

```bash
python -m compileall ESTER
python -m compileall modules
```

## Ignore Proof

- [ ] Create `.env` and `data/test.jsonl`.
- [ ] Run `git check-ignore -v .env data/test.jsonl`.
- [ ] Output shows `.gitignore` rules.
- [ ] Cleanup temporary files.

## Staged Blob Gate Proof

- [ ] Stage touch list plus writer.
- [ ] Print staged line counts for all gated files.
- [ ] Verify CR is absent in key staged files.

## Push Readiness

- [ ] There are staged changes to commit.
- [ ] Commit message is exact and auditable.
- [ ] Push only after every gate reports PASS.

## Iter12 Release Record (v0.2.0)

- Tag: `v0.2.0`
- Commit hash: `<fill-after-commit>`
- Release URL: `<fill-after-release>`
- Security hardening items:
  - JWT hardcoded fallback removed
  - Telegram token-tail logging removed
  - Private LAN default removed from role router defaults

## Iter13 Release Record (v0.2.1)

- Tag: `v0.2.1`
- Commit hash: `<fill-after-commit>`
- Release URL: `<fill-after-release>`
- Hygiene items:
  - Removed tracked generated reports from repository tracking
  - Removed tracked patch-output backup/rollback artifacts
  - Strengthened `.gitignore` report/patched artifact rules

## Iter14 Release Record (v0.2.2)

- Tag: `v0.2.2`
- Commit hash: `<fill-after-commit>`
- Release URL: `<fill-after-release>`
- Safety items:
  - Added explicit opt-in gates for auto-task generation
  - Added explicit opt-in gates for self-evo forge entrypoints
  - Added witness and risk-acknowledgement fail-closed prerequisites

## Iter15 Release Record (v0.2.3)

- Tag: `v0.2.3`
- Commit hash: `<fill-after-commit>`
- Release URL: `<fill-after-release>`
- Documentation items:
  - Rewrote autonomy policy docs into strict multiline format
  - Added quick operator env snippet and disabled/missing-prereqs examples
  - Added staged doc gate to prevent minification regressions

## Iter16 Release Record (v0.2.4)

- Tag: `v0.2.4`
- Commit hash: `<fill-after-commit>`
- Release URL: `<fill-after-release>`
- Stability items:
  - Repointed public stable download links from old `v0.2.3` snapshots to the new stable tag
  - Published the current `main` code state as a new stable release instead of rewriting the old tag
  - Included the public-safe document recall layer in the stable snapshot
