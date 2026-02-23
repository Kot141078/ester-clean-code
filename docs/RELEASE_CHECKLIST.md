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
