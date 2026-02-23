# Ester Clean Code - v0.2.0

## Summary

This release completes final public hardening for authentication, logging hygiene, and peer defaults.
The repository is published as clean code only, with runtime/state/secrets excluded by policy.

## Highlights

- JWT signing now requires explicit operator-provided secret by default.
- Dev mode supports ephemeral JWT secret only with `ESTER_DEV_MODE=1`.
- Telegram adapter startup log no longer prints token tail fragments.
- Role router peer default is env-driven (`ESTER_ROLE_ROUTER_URL`) with localhost fallback.
- `.gitignore` switched to standard runtime/secrets exclusions for full clean-tree publication.

## Security and Privacy

- No secrets, runtime data, or operational logs are intended to be committed.
- Token substring logging has been removed from startup telemetry.
- JWT secret fallback hardcode has been removed; default behavior is fail-closed if secret is missing.

## L4W Alignment Statement

This release preserves L4W witness-first constraints:
identity and privileges are explicit, actions remain auditable, budgets and controls are enforceable,
and uncertain policy state should degrade to fail-closed behavior.

## What's Not Included

- `.env` and other secret material
- runtime data under `data/`, `state/`, `logs/`
- scrolls/vector stores and derived local artifacts

## Verification

Commands executed for this release:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\scan_repo.ps1 -Root .
```

```bash
python -m compileall ESTER
python -m compileall modules
```

```powershell
git check-ignore -v .env data\test.jsonl
```

All checks: PASS.

## Related Public Corpus

- AGI v1.1 release: https://github.com/Kot141078/advanced-global-intelligence/releases/tag/v1.1
- ester-reality-bound: https://github.com/Kot141078/ester-reality-bound
- sovereign-entity-recursion: https://github.com/Kot141078/sovereign-entity-recursion
