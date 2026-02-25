# Iter47: Drift Quarantine

## What Quarantine Solves

`capability_drift` detects silent privilege drift, but detection alone is not enough.
`drift_quarantine` adds an enforcement layer:

- HIGH drift marks agent as quarantined.
- In Slot B, quarantined agents are blocked on enqueue/execute.
- Unblock requires explicit manual confirmation via `drift.quarantine.clear`.

## What Is HIGH Drift

Quarantine currently triggers on escalation-class drift:

- `SPEC_MISMATCH` with extra actions in stored allowlist vs computed allowlist:
  - reason: `TAMPER_SUSPECT`
  - severity: `HIGH`
- `ALLOWLIST_CHANGED` where baseline (`last_seen`) -> current computed gains actions:
  - reason: `ESCALATION`
  - severity: `HIGH`

Shrink-only drift does not quarantine.

## Storage

State and logs are in `data/capability_drift/`:

- `quarantine_state.json`:
  - bounded map by `agent_id`
  - contains active state, event metadata, and clear metadata
- `quarantine_events.jsonl`:
  - append-only
  - event types:
    - `QUARANTINE_SET`
    - `QUARANTINE_BLOCK`
    - `QUARANTINE_CLEAR`

State size is bounded by `ESTER_QUARANTINE_MAX_STATE` (default `5000`).

## Enqueue and Execute Blocking

Slot behavior:

- Slot A:
  - observe-only
  - quarantine may be set and shown in status
  - enqueue/execute are not blocked
- Slot B:
  - enforce mode
  - enqueue returns `DRIFT_QUARANTINED`
  - runner blocks before execution with `DRIFT_QUARANTINED`

Fail-closed behavior:

- if subsystem fails in Slot B and not yet rolled back, it prefers deny.
- repeated failures trigger in-process rollback to Slot A.

## Manual Clear via Action

Action id:

- `drift.quarantine.clear`

Required args:

- `agent_id`
- `event_id` (must match current active quarantine event id)
- `reason` (human-readable)

Optional:

- `by`
- `chain_id`

Call path should be `invoke_guarded`, so volition decision and rationale are journaled.

Example:

```python
from modules.thinking import action_registry

rep = action_registry.invoke_guarded(
    "drift.quarantine.clear",
    {
        "agent_id": "<agent_id>",
        "event_id": "<event_id>",
        "reason": "manual review approved",
        "by": "operator",
        "chain_id": "chain_quarantine_clear_001",
    },
)
```

## Runtime Status View

`/debug/runtime/status` includes `drift_quarantine`:

- `ok`, `slot`, `enforced`, `degraded`, `error`
- `summary`:
  - `active`, `cleared`
  - `set_recent`, `block_recent`
  - `last_set_ts`, `last_block_ts`
- `last_event`
- `active_agents_sample` (max 20)
- `perf`:
  - `cache_ttl_sec`, `build_ms`
  - `state_size`, `tail_lines`
  - `fail_streak`, `fail_max`
  - `mode_forced`, `last_rollback_reason`

## Bridges

Explicit bridge (safety engineering):
Circuit breaker / quarantine. Detection without reaction is post-incident monitoring; quarantine turns drift into a controlled incident.

Hidden bridge #1 (information theory):
Bounded response. Quarantine limits attack/error throughput by freezing one compromised agent instead of letting it fan out.

Hidden bridge #2 (physiology):
Immunity and isolation. Suspected infection is isolated before full diagnosis to prevent systemic spread.

## Earth Paragraph

It’s like security and quarantine at a facility: if an employee suddenly has a key to a critical area without registration,
he is not allowed beyond the turnstile, even if he has an “outfit.” First, manual verification and signature of the person responsible.
This way the incident does not become an accident.

