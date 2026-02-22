# Architecture Overview

## Why This Exists

Ester is an accountable operations core.
Ester is not a conversation-first chatbot.

The architecture is tuned for constrained execution,
auditable actions,
and explicit governance boundaries.

## Core Equation

- `c = a + b`
- `a`: responsible human anchor.
- `b`: bounded procedures plus technical controls.
- `c`: accountable entity behavior.

## L4 Reality Boundary

L4 means real-world constraints are part of safety logic.

- time limits matter,
- spend limits matter,
- rate limits matter,
- access limits matter,
- irreversible effects matter.

## Layering

- **L3**: policy, legal language, and process declarations.
- **L4**: operational and physical constraints.
- **L4W**: L4 plus witness-first accountability controls.

## Trust Boundaries

- `ESTER/**` runtime and route surface.
- `modules/**` subsystem implementations.
- `docs/**` governance and operator docs.
- `tools/**` local verification and scanners.

## Safety Defaults

- explicit identity for privileged operations,
- explicit least-privilege grants,
- durable witness trail,
- deterministic release checks,
- fail-closed behavior under ambiguity.

## Rights Boundary

Code is AGPL-licensed.
Name/logo rights are separate and trademark-governed.

## Operational Consequence

No single layer is trusted in isolation.
Policy, code, and release checks must stay consistent.
