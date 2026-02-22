# L4W Alignment (Witness-First Norms)

## Definition

L4W combines L4 Reality Boundary with witness-first accountability.
Privileged actions must be attributable, bounded, and reviewable.

## Norm 1: Identity

The acting identity is explicit for privileged operations.
Anonymous high-impact behavior is out of policy.

## Norm 2: Auditable Privileges

Granted capabilities are explicit and least-privilege.
Unreviewed privilege expansion is treated as drift.

## Norm 3: Witness Trail

Actions produce durable evidence.
Evidence must support tamper-evident review.
No-witness privileged paths are unsafe.

## Norm 4: Budgets

Time, spend, and rate budgets are mandatory controls.
Budget overflow requires stop or escalation.

## Norm 5: Veto and Challenge Window

Humans can veto risky actions before irreversible commit.
Disputed actions require a defined challenge window.

## Norm 6: Fail-Closed

Ambiguous policy state resolves to safer behavior.
Default behavior is deny or pause.

## Bridge Requirements

- Explicit bridge: identity + auditable privileges + witness trail.
- Hidden bridge A: Ashby variety requirement.
- Hidden bridge B: Cover and Thomas information constraint.

## Implementation Expectations

- identity checks run before privileged action,
- privilege grants are explicit and reviewable,
- witness records survive process restarts,
- budget gates are enforced before execution,
- veto and challenge windows are documented.

## Non-Claims

- No autonomy guarantee.
- No perfect containment guarantee.
- No perfect safety claim.
