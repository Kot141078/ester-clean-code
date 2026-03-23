# Entity-centered runtime hierarchy

## Rule

By default, `c` orchestrates agents; agents do not define `c`.

## Runtime meaning

Agents are subordinate runtime processes. They may retrieve, judge, plan, call tools, or execute bounded work. They are selected, bounded, and stopped under `c`.

## Continuity boundary

Continuity does not belong to any single model, provider, worker, or judge. Replacing a model or rotating a worker does not by itself redefine the entity.

## Privilege boundary

Agents do not hold open-ended authority. Privileges are delegated under explicit scope, budgets, and fail-closed gates. `c` is the runtime layer that must preserve the human anchor's intent through this delegation.

## Non-goal

This repository does not define an agent swarm as the primary subject. Agents are execution surfaces. The entity remains `c = a + b`.
