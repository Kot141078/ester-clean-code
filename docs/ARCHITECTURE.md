# Architecture Overview

## The Point
Ester is built for accountable operations:
- a human anchor remains responsible,
- capabilities are explicit,
- actions leave a witness trail.

## Layers (Operational)
- **L3:** text rules, policies, legal framing.
- **L4:** physical and operational constraints (time, energy, access, irreversibility).

## Repository Boundaries
- Public source targets: `ESTER/**`, `modules/**`.
- Runtime artifacts are excluded by design (`data/`, `state/`, `logs/`, scrolls, vector DBs).

## Safety Defaults
- least privilege,
- deny-by-default for risky I/O,
- explicit escalation.
