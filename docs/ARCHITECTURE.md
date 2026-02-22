# Architecture Overview

## Mission Context

Ester is not a chatbot.
Ester is an accountable operations core designed for long-lived local-first execution.

## Core Equation

- c = a + b
- `a`: responsible human anchor
- `b`: bounded procedures, policy, and tooling
- `c`: accountable entity behavior under constraints

## L4 Reality Boundary

L4 means physical and operational constraints are explicit safety inputs.
Time, energy, network scope, budget, and irreversibility all affect allowed actions.

## Layering Model

- **L3**: legal text, process rules, policy wording.
- **L4**: real-world constraints and irreversible effects.
- **L4W**: L4 plus witness trail and human challenge controls.

## Trust Boundaries

- `ESTER/**`: application runtime surface.
- `modules/**`: internal subsystem code.
- `docs/**`: policy and operational documentation.
- `tools/**`: local safety instrumentation and validation.

## Execution Guarantees (Repository Level)

- Privileges should be explicit and least-privilege by default.
- High-risk operations should be auditable after the fact.
- Uncertainty should degrade to fail-closed behavior.

## Data Boundaries

The clean-code repository excludes runtime state, private logs, secrets, and personal datasets.
Those artifacts belong outside versioned public source trees.

## Branding Boundary

Code rights are AGPL.
Name/logo rights are separate and governed by trademark policy.

## Design Implication

No single file is trusted in isolation.
Policy, code, scanner gates, and release checks must agree before publish.
