# Iter46: Capability Drift Detector

## What Drift Means and Why It Matters

`capability_drift` detects silent privilege changes across time and state representations:

- `computed_allowlist` (derived from template/capabilities)
- `stored_allowlist` and `stored_allowlist_hash` in agent spec
- `last_seen` baseline of previously observed computed authority

If these diverge unexpectedly, integrity and policy guarantees are no longer trustworthy.

## Comparisons Performed

For each scanned agent:

- `SPEC_MISMATCH`: `computed_hash != stored_hash`
- `ALLOWLIST_CHANGED`: `last_seen.allowlist_hash != computed_hash`
- `CAPS_CHANGED`: `last_seen.caps_hash != current_caps_hash`

Hashing and diff are deterministic:

- `normalize_allowlist(list)`: sorted + unique
- `allowlist_hash(list)`: `sha256(canonical_json(normalized_list))`
- `added`/`removed`: bounded to max 10 items each

## Storage Layout

Data is under `data/capability_drift/`:

- `events.jsonl` append-only drift events
- `last_seen.json` bounded map by `agent_id`

`last_seen` keeps at most `ESTER_DRIFT_MAX_LAST_SEEN` (default `5000`), compacting by newest `ts`.

## Status Block

`/debug/runtime/status` now includes `capability_drift`:

- `ok`, `slot`, `degraded`, `error`
- `summary`:
  - `scanned_agents`, `scan_limited`
  - `mismatched`, `change`, `caps changed`, `escalations`
  - `last_event_ts`
- `last_event`
- `recent_events` (max 10 in Slot B)
- `perf`:
  - `cache_ttl_sec`, `build_ms`
  - `last_seen_size`, `events_tail_lines`
  - `fail_streak`, `fail_max`, `mode_forced`

## Slot Modes and Rollback

- Slot A:
  - only `computed vs stored` mismatch counters
  - no `last_seen` writes
  - no drift event writes
- Slot B:
  - `last_seen` baseline comparison
  - append-only drift events

In-process controls:

- cache TTL: `ESTER_DRIFT_TTL_SEC` (default `5`)
- fail max: `ESTER_DRIFT_FAIL_MAX` (default `3`)

If Slot B repeatedly fails (IO/parsing/runtime), mode is forced to Slot A until process restart.

## Running the Tool

Smoke:

- `python -B tools/capability_drift_smoke.py`

Offline suite:

- `powershell -File tools/run_checks_offline.ps1 -NoGitGuard -Quiet`

## Bridges

Explicit bridge (security engineering):
Integrity monitoring is mandatory. Policy without integrity checks is an illusion.

Hidden bridge #1 (information theory):
Observation bandwidth is bounded; tail reads plus bounded last_seen prevent monitoring from becoming load amplification.

Hidden bridge #2 (physiology):
Homeostasis requires sensors. Without drift sensing, the system adapts to corruption as if it were normal.

## Earth Paragraph

It’s like control of seals and a log of access: it’s not enough to issue the keys once - you need to check
Has the “cutting of keys” itself changed? Drift detector is a regular verification:
if an employee suddenly has a key to the electrical panel without registration, this is caught immediately, and not after the accident.

