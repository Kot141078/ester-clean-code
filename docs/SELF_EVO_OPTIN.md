# Self-Evo and Autonomy Opt-In Policy

## Default Posture

Autonomy amplification features are OFF by default.

- Auto initiative queue generation is disabled unless explicitly enabled.
- Self-evo forge entrypoints are disabled unless explicitly enabled.
- Missing prerequisites always resolve to no-op with explicit status (`fail-closed`).

## Why OFF By Default

These pathways can increase action velocity and irreversibility.
L4/L4W safety requires explicit identity, auditable privileges, witness trail, budgets, and a veto/challenge window before autonomous amplification is allowed.

## How To Enable

Set all required flags deliberately:

- `ESTER_ENABLE_AUTO_TASKS=1` to allow initiative queue generation.
- `ESTER_ENABLE_SELF_EVO=1` to allow self-evo forge entrypoints.
- `ESTER_ACK_AUTONOMY_RISK=I_UNDERSTAND` to acknowledge operator risk.
- `ESTER_L4W_WITNESS=1` or runtime witness readiness.

For auto-task generation, provide budgets either in call parameters or env fallback:

- `ESTER_AUTO_TASKS_MAX_ITEMS`
- `ESTER_AUTO_TASKS_WINDOW`
- `ESTER_AUTO_TASKS_MAX_WORK_MS`

## Prerequisites Checklist

- Identity: actor identity is explicit.
- Privileges: privileged operations are auditable and least-privilege.
- Witness: witness trail is present and ready.
- Budgets: max items, time window, and max work budget are bounded.
- Veto window: challenge and stop paths exist before irreversible action.

## Failure Mode

If any prerequisite is missing, features stay OFF and return explicit disabled status.
No queue writes or self-evo apply actions are performed.

## Bridge Framing

Explicit bridge:
- identity + auditable privileges + witness trail.

Hidden bridge A (Ashby):
- controller variety must match disturbance variety; otherwise disable amplification.

Hidden bridge B (Cover/Thomas):
- ambiguity lowers signal quality; uncertainty must degrade to safer defaults.

## Earth Paragraph

Runaway autonomy loops resemble tachycardia: rate rises, control quality falls, and recovery narrows.
Budgets and witness-gated opt-in act like a pacemaker, forcing bounded cadence and auditable intervention points.
