# Changelog

## [Unreleased]

## [0.2.5] - 2026-04-11
### Privacy/Hygiene
- Removed tracked root-level runtime and debug dump artifacts from the public tree.
- Added a tracked-files privacy scanner and a public release safety gate.
- Hardened ignore and export rules to block common runtime, dump, and secret artifacts from re-entering the repository.

### Release Truth
- Aligned `VERSION`, `release/VERSION`, and stable download references to `v0.2.5`.
- Added `docs/RELEASE_NOTES_v0.2.5.md` to document the cleanup and release posture.
- Kept the already-published `v0.2.4` tag untouched for auditability.

### CI/Workflow
- Removed the malformed `lint-and-tests.yml` workflow and kept `ci.yml` as the canonical CI workflow.
- Strengthened the publish sanitizer to fail closed on dirty trees and release-safety gate failures.

## [0.2.3] - 2026-02-24
### Documentation
- Rewrote opt-in autonomy docs as strict multiline Markdown for audit readability.
- Added quick operator env snippet and fail-closed status examples for disabled and missing-prereqs states.
- Added staged doc gate script to prevent readability drift-by-minification in staged blobs.

### Safety
- Safety posture unchanged: autonomy defaults remain OFF and prereq failures stay fail-closed.

## [0.2.2] - 2026-02-24
### Safety
- Added explicit opt-in gates for initiative auto-task generation.
- Added explicit opt-in gates for self-evo forge entrypoints.
- Enforced fail-closed prerequisites: risk acknowledgement, witness readiness, and required budgets for auto-tasking.

### Documentation
- Added `docs/SELF_EVO_OPTIN.md` with enablement policy and prerequisites.
- Updated `README.md`, `docs/README.md`, and `docs/THREAT_MODEL.md` to document autonomy amplification controls.

## [0.2.1] - 2026-02-23
### Hygiene
- Removed tracked generated reports and patch-output artifacts from version control.
- Strengthened `.gitignore` rules to block report and patched-output artifacts.

### Notes
- No functional changes.

## [0.2.0] - 2026-02-23
### Security
- Removed insecure hardcoded JWT fallback and switched to explicit secret configuration with fail-closed behavior.
- Removed Telegram token tail logging; startup logs now report configured yes/no only.

### Hygiene
- Removed private LAN peer default from role router and switched to env-driven endpoint with localhost default.
- Replaced deny-by-default `.gitignore` allowlist with standard runtime/secrets ignores for full clean-tree publishing.

### Documentation
- Added `docs/RELEASE_NOTES.md` as release title page.
- Updated `docs/RELEASE_CHECKLIST.md` for this release.
- Bumped `CITATION.cff` version metadata.

## [0.1.0] - 2026-02-22
### Added
- Initial clean-code release scaffold (AGPL + policies).
