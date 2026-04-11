# Ester Clean Code — v0.2.5

## Summary

This release publishes a privacy-clean and release-consistent stable snapshot from the current `main` branch.
It adds deterministic release-safety gates and removes tracked runtime residue from the public tree without rewriting the older `v0.2.4` tag.

## What Changed

### Privacy / Hygiene

- Removed tracked root-level runtime and debug dump artifacts:
  - `.ester_env_state.json`
  - `qa.json`
  - `resp.json`
  - `dod_status.json`
  - `net_search_log_dump.json`
- Added `tools/privacy_scan.py` to scan tracked files only and fail closed on critical findings.
- Hardened `.gitignore` and source export rules for runtime, dump, and secret-shaped artifacts.
- Replaced machine-specific local path references in release-facing and launcher-adjacent files with portable paths or explicit placeholders.

### Release Truth

- Aligned `VERSION` and `release/VERSION` to `v0.2.5`.
- Updated `README.md`, `MACHINE_ENTRY.md`, and `llms.txt` so stable download references match the new tag.
- Added a release-safety gate to verify privacy status, workflow validity, release metadata coherence, and tracked hash manifests before publication.

### CI / Workflow

- Removed the malformed `.github/workflows/lint-and-tests.yml` file.
- Kept `.github/workflows/ci.yml` as the canonical CI workflow.
- Hardened `tools/publish/sanitize_and_publish.ps1` so it fails closed on dirty trees and safety-gate failures, and no longer defaults to force-push.

## Verification

- `python tools/privacy_scan.py`
- `python tools/check_public_release_safety.py --expected-tag v0.2.5`
- `python -m compileall ESTER`
- `python -m compileall modules`
- `python -m compileall tools`
- `python -m pytest tests/test_retrieval_router_doc_resolution.py -q`
- `python -m pytest tests/test_doc_lookup_semantic.py -q`

## Notes

- `v0.2.4` remains unchanged for auditability.
- This release note does not claim success beyond the checks listed above; the public safety gate and manual audit must both pass before tagging.
