# Changelog

## [Unreleased]

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
