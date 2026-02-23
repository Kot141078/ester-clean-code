# Iter45: Capability Audit View

## What Was Added to `/debug/runtime/status`

`modules/runtime/status_iter18.py` now appends a new section:

- `capability_audit.ok`
- `capability_audit.slot`
- `capability_audit.degraded`
- `capability_audit.error`
- `capability_audit.agents`
- `capability_audit.clamp`
- `capability_audit.deny`
- `capability_audit.recent_events` (max 30)
- `capability_audit.perf`

The route itself was not changed; only the payload builder was extended.

## Agent Classification Rules

The audit scans saved agent specs (stable sort by `agent_id`) and classifies each scanned agent as:

- `capability_mode`: `template_id != ""` and effective capabilities are present (or `authority_source == "template.capabilities"`).
- `template_legacy`: `template_id != ""` and effective capabilities are empty.
- `raw_capabilities`: `template_id == ""` and effective capabilities are present.
- `pure_legacy`: no `template_id` and no effective capabilities.

Scan controls:

- `ESTER_CAP_AUDIT_MAX_AGENTS_SCAN` (default `2000`)
- If there are more agents than this limit, only first `N` are counted, `degraded=true`, and `perf.scanned_agents=N`.

## Journal Tail Parsing and Safety

In Slot B, the audit reads only the tail of volition journal JSONL:

- `ESTER_CAP_AUDIT_TAIL_LINES` (default `2000`)
- invalid JSON lines are skipped
- no full-log scan on each call

Events extracted:

- deny: `agent.create` / `agent.queue.enqueue` / `agent.run.step` with `allowed=false`
- clamp: `agent.create` with `allowed=true` and clamp signal (`reason_code` contains `CLAMP` and/or `metadata.warnings`)

Telemetry includes:

- recent deny/clamp totals
- last event fields
- `by_code` counters by `reason_code` (plus clamp warning codes)
- last 30 normalized events in `recent_events`

## Slot B and Auto-Rollback

`modules/runtime/capability_audit.py` adds in-process cache and rollback controls:

- cache TTL: `ESTER_CAP_AUDIT_TTL_SEC` (default `5`)
- failure threshold: `ESTER_CAP_AUDIT_FAIL_MAX` (default `3`)

If Slot B audit building throws repeated errors, mode is forced to Slot A in-process. Status exposes this through:

- `capability_audit.degraded`
- `capability_audit.error`
- `capability_audit.audit_mode_forced`
- `capability_audit.audit_last_rollback_reason`
- `capability_audit.perf.fail_streak`
- `capability_audit.perf.fail_max`

## Bridges

Explicit bridge (security/audit):
You can't secure what you can't observe. Capability enforcement without visibility into clamp/deny paths is trust, not verification.

Hidden bridge #1 (information theory):
Observation bandwidth is limited. Tail-read + cache keeps the monitor itself from becoming a load amplifier.

Hidden bridge #2 (physiology):
Safe control loops need proprioception. Clamp/deny telemetry is operational feedback for policy and execution loops.

## Earth Paragraph

Eto kak panel OTK na proizvodstve: malo postavit ogranichiteli na stanki — nuzhno videt, skolko raz okhrana razvorachivala lyudey,
gde chasche vsego pytayutsya zayti “ne v tu zonu” i kakie propuska prikhoditsya urezat. Inache bezopasnost est “na bumage”, a ne v tsekhu.

