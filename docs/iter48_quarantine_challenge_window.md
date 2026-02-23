# Iter48: Quarantine Challenge Window

## What It Is

Iter48 adds a deterministic challenge window to drift quarantine:

- On `QUARANTINE_SET`, runtime stores `challenge_open_ts`, `challenge_sec`, and `challenge_deadline_ts`.
- Until manual clear, agent remains blocked in Slot B exactly as in Iter47.
- If deadline passes without clear, runtime records a one-time `QUARANTINE_EXPIRED` event and marks state as expired.
- There is no auto-unblock. Manual clear is still required.

## New State Fields

Each row in `data/capability_drift/quarantine_state.json` now includes:

- `challenge_open_ts: int`
- `challenge_deadline_ts: int`
- `challenge_sec: int` (`ESTER_QUARANTINE_CHALLENGE_SEC`, default `3600`, min clamp `60`)
- `expired: bool`
- `expired_ts: int`
- `expired_event_id: str`

`cleared` also stores audit fields:

- `on_time: bool`
- `late: bool`
- `deadline_ts: int`
- `cleared_ts: int`

## When `QUARANTINE_EXPIRED` Is Written

Runtime emits `QUARANTINE_EXPIRED` when all conditions hold:

- quarantine row is active,
- `now > challenge_deadline_ts`,
- `expired_event_id != current event_id`.

After emission, state is updated with:

- `expired=true`,
- `expired_ts=now`,
- `expired_event_id=current event_id`.

This guarantees one `QUARANTINE_EXPIRED` per quarantine `event_id`.

## Reading Runtime Status

`/debug/runtime/status` (`drift_quarantine` block) now exposes:

- `summary.active_open`: active rows with deadline not reached.
- `summary.active_expired`: active rows with deadline already passed.
- `summary.cleared_on_time` and `summary.cleared_late`.
- `summary.last_expired_ts`.

`active_agents_sample[]` includes:

- `challenge_deadline_ts`
- `challenge_remaining_sec` (time left before deadline)
- `expired`
- `overdue_sec` (time elapsed after deadline)

Interpretation:

- `challenge_remaining_sec > 0` and `overdue_sec = 0` => challenge window still open.
- `challenge_remaining_sec = 0` and `overdue_sec > 0` => challenge window expired.

## Manual Clear Example

```python
from modules.thinking import action_registry

rep = action_registry.invoke_guarded(
    "drift.quarantine.clear",
    {
        "agent_id": "<agent_id>",
        "event_id": "<current_quarantine_event_id>",
        "reason": "manual review completed",
        "by": "operator",
        "chain_id": "chain_manual_clear_001",
    },
)

# rep contains:
# rep["on_time"] / rep["late"]
# rep["deadline_ts"]
# rep["cleared_ts"]
```

`QUARANTINE_CLEAR` event details now include these same timing fields for audit trails.
