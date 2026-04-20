# Sanitary Transfer 2026-04-20

This document records the curated code-only transfer from the private Ester runtime into `ester-clean-code`.

## Goal

Transfer only implementation improvements that are:

- privacy-safe
- runtime-agnostic
- compatible with the public clean-code skeleton
- disabled or fail-closed by default where autonomy is involved

## Applied

- Telegram document-flow parity fixes:
  - honest separation between processing failure and delivery failure
  - retry-backed document notices
  - shared passport short-term restore normalizer
- Bounded agent planning improvements:
  - `modules/proactivity/role_allocator.py`
  - `modules/proactivity/planner_v2.py`
  - executor fallback chain `planner_v2 -> planner_v1`
  - agent-goal template selection can consult the role allocator
- Tests for the transferred code

## Explicitly Not Transferred

- private runtime data
- memory files
- vector memory
- generated telemetry snapshots
- backup folders
- sister packs
- live journals from the private instance
- local machine paths and operational traces

## Safety Rules

- Keep autonomy-related behavior disabled by default.
- Do not let agent infrastructure rewrite identity, memory, dream, recall, or reply-path semantics.
- Treat all public transfers as code-only unless explicitly reviewed otherwise.

## Deferred

These private-runtime additions were intentionally left out of the clean repo in this pass:

- sister handoff/export packaging
- live swarm telemetry snapshots
- private operator-facing runtime artifacts
- deeper swarm execution/report layers that are useful only with a specific live deployment envelope

## Verification Target

Run only local code checks and tests for the transferred subset.

