# Self-Evo and Autonomy Opt-In Policy

## Default Posture

Autonomy amplification features are OFF by default.

- Auto initiative queue generation is disabled unless explicitly enabled.
- Self-evo forge entrypoints are disabled unless explicitly enabled.
- Missing prerequisites always resolve to no-op with explicit status (`fail-closed`).

## Why OFF By Default

These pathways can increase action velocity and irreversibility.
L4/L4W safety requires identity, auditable privileges, witness trail, budgets, and a veto or challenge window before autonomous amplification is allowed.

## Enable Checklist (Exact Flags)

Set all required flags explicitly:

- `ESTER_ENABLE_AUTO_TASKS=1`
- `ESTER_ENABLE_SELF_EVO=1`
- `ESTER_ACK_AUTONOMY_RISK=I_UNDERSTAND`
- `ESTER_L4W_WITNESS=1` (or runtime witness-ready signal)

For auto-task generation, required budgets must be present either in call parameters or env fallback:

- `ESTER_AUTO_TASKS_MAX_ITEMS`
- `ESTER_AUTO_TASKS_WINDOW`
- `ESTER_AUTO_TASKS_MAX_WORK_MS`

Minimal operator snippet:

```bash
export ESTER_ENABLE_AUTO_TASKS=1
export ESTER_ENABLE_SELF_EVO=1
export ESTER_ACK_AUTONOMY_RISK=I_UNDERSTAND
export ESTER_L4W_WITNESS=1
export ESTER_AUTO_TASKS_MAX_ITEMS=5
export ESTER_AUTO_TASKS_WINDOW=60
export ESTER_AUTO_TASKS_MAX_WORK_MS=2000
```

## Fail-Closed Behavior

If any prerequisite is missing, features remain OFF.
No queue writes or self-evo apply actions are performed.

Disabled by default status example:

```json
{"ok": true, "enabled": false, "reason": "disabled_by_default", "created": []}
```

Enabled but missing prerequisites status example:

```json
{"ok": true, "enabled": false, "reason": "missing_prereqs", "missing": ["ACK", "WITNESS", "BUDGETS"]}
```

## Prerequisites (Operational)

- Identity: actor identity is explicit.
- Privileges: privileged operations are auditable and least-privilege.
- Witness: witness trail is present and ready.
- Budgets: max items, time window, and max work budget are bounded.
- Veto window: challenge and stop paths exist before irreversible action.

## Bridge Framing

Explicit bridge:

- identity + auditable privileges + witness trail.

Hidden bridge A (Ashby):

- controller variety must match disturbance variety; otherwise disable amplification.

Hidden bridge B (Cover/Thomas):

- ambiguity lowers signal quality; uncertainty must degrade to safer defaults.

## Earth Paragraph

Runaway autonomy loops resemble tachycardia:
rate rises, control quality falls, and recovery narrows.
Budgets plus witness-gated opt-in act like a pacemaker,
forcing bounded cadence and auditable intervention points.
