# Threat Model (Practical)

## Scope

This model covers repository and release workflow risks.

## Threat 1: Secret Leakage

- Risk: keys, tokens, or personal identifiers enter tracked files.
- Impact: credential abuse, privacy breach, legal exposure.
- Control: deny-by-default ignore policy and scanner gate.

## Threat 2: Privilege Drift

- Risk: capability grows without explicit review.
- Impact: unauthorized or irreversible behavior.
- Control: explicit privilege mapping with human escalation.

## Threat 3: Covert Network Paths

- Risk: undeclared outbound calls bypass policy.
- Impact: data exfiltration and hidden dependencies.
- Control: local-first defaults and auditable scripts.

## Threat 4: Audit Gaps

- Risk: actions occur without durable evidence.
- Impact: disputes become unresolvable.
- Control: witness trail requirements and release gates.

## Threat 5: Hidden Fragmentation

- Risk: invisible background delegation alters behavior.
- Impact: nondeterministic operations and accountability loss.
- Control: explicit task flow and no-background-task rule.

## Threat 6: Retry Storms and Silent Escalation

- Risk: failures loop without intervention.
- Impact: budget burn and policy violations.
- Control: hard stops, budget caps, and fail-closed defaults.

## Detection Signals

- unexpected privilege expansion,
- undeclared outbound network calls,
- missing witness records,
- repeated retries past budget threshold,
- policy text and executable checks drifting apart.

## Residual Risk

Residual risk remains.
It is managed through conservative defaults,
repeatable local checks,
and explicit human review points.
