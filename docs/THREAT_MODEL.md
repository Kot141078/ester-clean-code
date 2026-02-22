# Threat Model (Practical)

## Scope

This model focuses on repository-level and workflow-level threats for public clean-code release.

## Threat 1: Secret Leakage

- Tokens, keys, certificates, or personal identifiers enter tracked files.
- Impact: credential abuse, privacy breach, legal exposure.
- Control: strict `.gitignore`, scanner gates, reviewer scrutiny.

## Threat 2: Privilege Drift

- Capability expands silently without policy alignment.
- Impact: unauthorized or irreversible actions.
- Control: explicit privilege model, documented escalation, human veto points.

## Threat 3: Covert Network Paths

- Hidden outbound calls bypass declared workflow constraints.
- Impact: data exfiltration or remote dependency risk.
- Control: local-first defaults, explicit network policy, reviewable scripts.

## Threat 4: Audit Gaps

- Actions occur without sufficient witness artifacts.
- Impact: disputes cannot be resolved and accountability collapses.
- Control: tamper-evident logs and deterministic release checks.

## Threat 5: Hidden Task Fragmentation

- Work is delegated to untracked background flows.
- Impact: unpredictable state and unverifiable change history.
- Control: no background tasks in release procedure; explicit command transcript.

## Threat 6: Infinite Retry and Silent Escalation

- Failure loops continue without human intervention.
- Impact: budget burn, noisy failures, accidental policy violation.
- Control: hard stop conditions, budget caps, fail-closed defaults.

## Residual Risk Statement

No static threat model is complete.
Residual risk is managed by conservative defaults and repeatable local gates.
