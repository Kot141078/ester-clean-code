# Ester Clean Code — v0.2.6

## Summary

This release publishes the public-safe M1 memory diagnostics and Ollama runtime helper slice now present on `main`.
It keeps the public repository limited to implementation code, tests, release metadata, and operator-safe status surfaces; live Ester memory payloads, runtime diagnostics, local logs, and private stores are not included.

## What Changed

### Memory / Diagnostics

- Added public-safe memory diagnostic materialization for reply traces, self-diagnostics, internal trace coverage, and memory status surfaces.
- Added resilient diagnostic write helpers for Windows environments where atomic file replacement can be denied by file scanners or readers.
- Added report/HTTP helpers for memory overview, health, timeline, operator status, reply trace, and self-diagnostics.

### Local Runtime

- Added UTF-8/bootstrap helpers for local startup paths.
- Added Ollama launcher, model helper scripts, and an OpenAI-compatible local proxy profile.
- Replaced machine-specific launcher defaults with portable user/profile-relative defaults or explicit placeholders.

### Release Hygiene

- Updated stable release links from `v0.2.5` to `v0.2.6`.
- Aligned `VERSION`, `release/VERSION`, and the public release-safety default tag.
- Sanitized public test/probe fixtures to avoid personal-looking data.

## Verification

- `python -m pytest tests/test_active_memory_context.py tests/test_bootstrap_venv_run.py tests/test_diagnostic_io.py tests/test_memory_core_sqlite.py tests/test_memory_honesty.py tests/test_memory_index.py tests/test_memory_index_refresh_hooks.py tests/test_memory_self_observation.py tests/test_memory_status_tool.py tests/test_profile_snapshot.py tests/test_recall_benchmark.py tests/test_recall_diagnostics.py tests/test_reply_contour_memory_probe.py tests/test_reply_trace.py tests/test_reports_memory_http.py tests/test_restart_continuity_benchmark.py tests/test_run_ester_utf8_contract.py tests/test_self_diagnostics.py tests/test_user_facts_store.py -q`
- `python tools/check_public_release_safety.py`
- `git diff --check`

## Notes

- `v0.2.5` remains unchanged for auditability.
- This release note describes only the public repository state; it does not publish private live memory or local runtime data.
