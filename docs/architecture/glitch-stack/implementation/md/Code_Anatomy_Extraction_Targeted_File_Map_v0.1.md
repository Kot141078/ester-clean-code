# Code Anatomy Extraction / Targeted File Map v0.1

**Status:** Targeted reading and integration map  
**Scope:** `ester-clean-code` public skeleton only (GitHub-compatible dump, not private production Ester)  
**Goal:** Identify the most relevant files and zones for implementing the new stack:

- `L4 Glitch Map`
- `ResearchNode / BackwardNode`
- `Cinematic Walkthrough Layer`
- `Witness Overlay / Evidence Notation`
- `Challenge / Review Protocol`
- `State Transition Matrix / Status Algebra`

---

## 1. Honest framing

This map is **not** a claim that the repository already contains all of these abstractions in finished form.

It is a **targeted extraction guide** based on the dump and manifest.

The dump is large:
- `3432` files
- `~12.6 MB`
- split into `7` parts

So the right method is not “read everything.”
The right method is: find the already-living anatomical zones where the new stack can attach with minimal violence.

---

## 2. What the dump already confirms

The public skeleton already contains real implementation terrain for:

- persistent memory
- route-level memory APIs
- runtime quarantine and challenge windows
- witness / evidence signing
- privilege and RBAC boundaries
- drift detection
- integrity / Merkle support
- observability and metrics
- explicit docs around capability drift, quarantine, challenge windows, evidence packets, and L4W

This is the key result.

The new stack is not floating above the codebase.
It already has places to land.

---

## 3. Highest-priority reading zones

## 3.1 Runtime collision / quarantine / challenge core

### Primary file
- `modules/runtime/drift_quarantine.py`

### Why this matters
This is the strongest currently visible candidate for the future:
- `GlitchNode` family,
- quarantine state,
- challenge window mechanics,
- evidence-path resolution,
- witness / signature requirements,
- rollback-to-A,
- fail-streak handling,
- expiry,
- drift classification.

### What is already visible
The file already contains:
- `_challenge_sec()`
- `_evidence_sig_required(slot)`
- `_l4w_required(slot)`
- `_l4w_chain_enforced(slot)`
- `_resolve_evidence_path(...)`
- `_failure_snapshot(...)`
- `_note_failure(...)`
- `_note_success(...)`
- `_state_row_defaults(...)`
- normalization of active / expired / cleared state
- evidence-related cleared fields
- challenge deadline timestamps
- challenge-open timestamps
- rollback reason tracking

### Why this is critical
This is the nearest existing anatomical zone to:

- `ResearchNode`
- `ChallengeRecord`
- `WitnessState`
- challenge lifecycle
- expire / settled / cleared mechanics

### Immediate reading priority
**Priority: P0**

---

## 3.2 Communication / time-boxed control windows

### Primary file
- `modules/runtime/comm_window.py`

### Why this matters
This file already implements:
- `open_window(...)`
- `is_open(...)`
- `close_window(...)`
- `list_windows()`

with:
- TTL,
- explicit expiry,
- reason,
- allowlist of hosts,
- persistent JSON state.

### Why it matters to the new stack
It is a ready anatomical precedent for:
- challenge windows,
- review windows,
- authority windows,
- time-boxed escalation lanes.

### Immediate reading priority
**Priority: P0**

---

## 3.3 Memory API / memory bridge

### Primary files
- `routes_memory.py`
- `routes_mem.py`
- `memory_manager.py`
- `memory.py`
- `memory_flashback.py`
- `modules.memory.facade` (seen through imports everywhere)

### Why this matters
These are the living bridges between:
- runtime state,
- flashback,
- aliasing,
- compaction,
- short/medium-term memory,
- and vector lookup.

### What is already visible
`routes_memory.py` already defines:
- `/memory/flashback`
- `/memory/stats`
- `/memory/alias`
- `/memory/compact`

with compatibility handling around different memory manager versions.

`routes_mem.py` provides a lighter `/mem/*` surface.

### Why this matters to the new stack
This is where:
- `ResearchNode` retrieval discipline,
- quarantine exclusion,
- reopenability queries,
- and graph-facing read models
will need to hook into memory without polluting execution paths.

### Immediate reading priority
**Priority: P0**

---

## 3.4 Chroma / vector store adaptation

### Primary file
- `modules/memory/chroma_adapter.py`

### Why this matters
Visible in the dump:
- env expansion hardening
- persist dir resolution
- auto-location of richest Chroma store
- collection probing
- `ChromaUI`
- add/search/list_recent/status surfaces

### Why this matters to the new stack
This is the likely entry zone for:
- quarantined research node storage
- graph search support
- evidence-linked semantic retrieval
- exclusion of speculative nodes from runtime execution retrieval

### Immediate reading priority
**Priority: P0**

---

## 4. Witness / evidence / signing zone

## 4.1 Local key and signing control

### Primary file
- `routes/admin_keys.py`

### Why this matters
This file already gives a visible local pattern for:
- key initialization
- signing test
- verification test
- Ed25519 / HMAC fallback handling
- public key display
- explicit offline trust control

### Why this matters to the new stack
It is a strong candidate for:
- witness packet sealing
- review outcome signatures
- evidence envelope UI bridges

### Immediate reading priority
**Priority: P1**

---

## 4.2 Merkle / integrity terrain

### Primary files
- `merkle/cas.py`
- `merkle/merkle_tree.py`
- `middleware/integrity_guard.py`

### Why this matters
These files likely form the lower-level integrity substrate for:
- content addressing
- evidence hash trees
- immutable-ish lineage checks

### Why this matters to the new stack
Future:
- `Witness Overlay`
- `Evidence Envelope`
- `Review split lineage`
- `historical branch preservation`

will all need integrity primitives.
This is the likely landing zone.

### Immediate reading priority
**Priority: P1**

---

## 4.3 L4W and quarantine docs already present

### High-value docs from the dump
- `docs/iter46_capability_drift_detector.md`
- `docs/iter47_drift_quarantine.md`
- `docs/iter48_quarantine_challenge_window.md`
- `docs/iter49_clear_requires_evidence_packet.md`
- `docs/iter50_integrity_stack.md`
- `docs/iter51_l4w_envelope.md`
- `docs/iter52_l4w_conformance_and_audit_cli.md`

### Why this matters
The public skeleton already documents a lot of the exact territory we are now formalizing conceptually:
- drift,
- quarantine,
- challenge windows,
- evidence packets,
- integrity stack,
- L4W envelope.

This is a big deal.

It means the bridge is not speculative.
The repository already grew nerves in that direction.

### Immediate reading priority
**Priority: P0**

---

## 5. Privilege / authority / guard zone

## 5.1 Middleware boundaries

### Primary files
- `middleware/rbac.py`
- `middleware/caution_guard.py`
- `middleware/hold_fire.py`
- `middleware/integrity_guard.py`
- `middleware/ingest_guard.py`
- `middleware/ingest_fair_guard.py`

### Why this matters
These are likely the best existing control points for:
- privilege locks
- fail-closed runtime refusal
- authority filtering
- execution boundary discipline

### Why this matters to the new stack
`GlitchNode` should not be born only from “errors.”
It should also emerge from:
- privilege refusal,
- caution halt,
- hold-fire state,
- integrity refusal,
- ingest guard refusal.

This middleware layer is therefore a natural source of typed L4 collisions.

### Immediate reading priority
**Priority: P0**

---

## 5.2 Unified will / guard surface

### Primary file
- `app_plugins/ester_will_unified_guard.py`

### Why this matters
Even from file naming alone, this looks like one of the most relevant future insertion points for:
- volitional boundary enforcement
- unified refusal
- authority discipline
- anti-bypass routing

### Why this matters to the new stack
If there is one place where `c`, privilege, refusal, and runtime action safety could meet,
this is likely near the center.

### Immediate reading priority
**Priority: P0**

---

## 6. Thinking / trace / read-only inspection zone

### Primary files
- `app_plugins/ester_thinking_trace_http.py`
- `app_plugins/ester_memory_flow_http.py`
- `docs/agent_activity.html`
- `docs/agent_report.html`
- `docs/agent_suite_index.html`
- `docs/agent_builder.html`

### Why this matters
These look like the most likely current read-model / visibility surfaces for:
- trace inspection
- memory flow visualization
- operator-facing introspection
- report generation

### Why this matters to the new stack
This is where the future:
- `Cinematic Walkthrough Layer`
- graph read models
- evidence overlay
- challenge visibility

can probably attach without touching execution authority.

### Immediate reading priority
**Priority: P1**

---

## 7. Agent / orchestration / capability zone

### Primary files
- `listeners/sidecar_orchestrator.py`
- `listeners/hybrid_job_router.py`
- `listeners/selfcare_scheduler.py`
- `judge_combiner.py`
- `group_intelligence.py`
- `group_digest.py`
- `daily_cycle.py`

### Why this matters
These files likely hold:
- orchestration,
- scheduling,
- routing,
- cross-component coordination,
- long-lived task circulation.

### Why this matters to the new stack
If `GlitchNode` and `ResearchNode` are to become system-wide rather than route-local,
the orchestration layer must know:
- how to stop,
- how to degrade,
- how to queue research,
- how not to relaunch forbidden branches blindly.

### Immediate reading priority
**Priority: P1**

---

## 8. Schema / status / transition zone

### High-likelihood zones from the tree
- `schemas/`
- `validator/`
- `rules/`
- `config/rbac_matrix.yaml`
- `config/rulehub.yaml`
- `config/synergy_policies.yaml`
- `config/privacy_policies.yaml`

### Why this matters
The new stack needs:
- enums
- tuple states
- legal/illegal transitions
- review admissibility
- execution gating

These zones are the most likely place where that can be typed and enforced.

### Why this matters to the new stack
This is where:
- `StatusTuple`
- `TransitionGuard`
- `Challenge admissibility`
- `ReopenabilityGate`
- `Evidence state legality`

should eventually become machine-checkable.

### Immediate reading priority
**Priority: P0 once file contents are isolated**

---

## 9. Graph / UI / rendering candidate zone

### Primary files / zones
- `templates/`
- `landing/`
- `static/`
- `docs/*.html`
- `ESTER/routes/*`
- `routes/*`

### Why this matters
The current skeleton already has a lot of operator/admin UI and route aliasing surfaces.

### Why this matters to the new stack
This is the likely home for:
- graph legend
- branch lane rendering
- evidence badges
- challenge markers
- audit-mode graph readouts

### Important warning
This must be **late-phase work**.

The repository already has enough UI to become dangerously persuasive if graph rendering comes before state algebra.

### Immediate reading priority
**Priority: P2**

---

## 10. Files to read first (strict short list)

If I had to choose the first **12** files to read in full for the real bridge, I would start here:

1. `modules/runtime/drift_quarantine.py`
2. `modules/runtime/comm_window.py`
3. `modules/memory/chroma_adapter.py`
4. `memory_manager.py`
5. `routes_memory.py`
6. `routes_mem.py`
7. `middleware/rbac.py`
8. `middleware/caution_guard.py`
9. `middleware/integrity_guard.py`
10. `app_plugins/ester_will_unified_guard.py`
11. `routes/admin_keys.py`
12. `docs/iter47_drift_quarantine.md`

Then immediately:

13. `docs/iter48_quarantine_challenge_window.md`
14. `docs/iter49_clear_requires_evidence_packet.md`
15. `docs/iter50_integrity_stack.md`
16. `docs/iter51_l4w_envelope.md`
17. `app_plugins/ester_thinking_trace_http.py`
18. `app_plugins/ester_memory_flow_http.py`
19. `listeners/sidecar_orchestrator.py`
20. `validator/*` and `rules/*` once isolated

---

## 11. Proposed future insertion points by concept

## 11.1 `GlitchNode`
Best first landing zone:
- `modules/runtime/drift_quarantine.py`
- plus middleware hooks from:
  - `rbac.py`
  - `caution_guard.py`
  - `integrity_guard.py`

## 11.2 `ResearchNode / BackwardNode`
Best first landing zone:
- `memory_manager.py`
- `modules/memory/chroma_adapter.py`
- storage separation under persistent memory layer
- docs + route read API second

## 11.3 `WitnessState`
Best first landing zone:
- `routes/admin_keys.py`
- integrity / merkle zone
- drift quarantine evidence packet structures

## 11.4 `ChallengeRecord / ReviewRecord`
Best first landing zone:
- `modules/runtime/drift_quarantine.py`
- `modules/runtime/comm_window.py`
- scheduler / expiry helpers
- docs/iter48 and iter49

## 11.5 `StatusTuple / TransitionGuard`
Best first landing zone:
- `validator/`
- `rules/`
- possibly a dedicated new status module
- tests as enforcement spine

## 11.6 `Graph read models`
Best first landing zone:
- `app_plugins/ester_thinking_trace_http.py`
- `app_plugins/ester_memory_flow_http.py`
- route-level read endpoints
- UI only after typed state exists

---

## 12. Red-line interpretation from the dump

The dump strongly suggests a repository that already values:

- local evidence
- explicit windows
- rollback
- drift detection
- role discipline
- challengeability
- and offline-safe trust control

That means the biggest danger now is **not missing philosophy**.

The biggest danger is:
implementing future graph or cinematic layers too early,
before the status and evidence objects become explicit enough.

So the correct order remains:

1. runtime / quarantine anatomy
2. evidence / witness anatomy
3. challenge / review anatomy
4. status algebra
5. read models
6. graph rendering
7. cinematic layer

---

## 13. What I would ask for next (targeted, not whole-repo)

Even with the full dump, the next *high-value* move would be to isolate and inspect the actual contents of:

- `modules/runtime/drift_quarantine.py`
- `modules/runtime/comm_window.py`
- `modules/memory/chroma_adapter.py`
- `memory_manager.py`
- `middleware/rbac.py`
- `middleware/caution_guard.py`
- `middleware/integrity_guard.py`
- `app_plugins/ester_will_unified_guard.py`
- `docs/iter47_drift_quarantine.md`
- `docs/iter48_quarantine_challenge_window.md`
- `docs/iter49_clear_requires_evidence_packet.md`
- `docs/iter50_integrity_stack.md`
- `docs/iter51_l4w_envelope.md`

Those are the anatomical nerves.

Everything else can wait.

---

## 14. Explicit bridge

The explicit bridge is now sharper than before:

**the public skeleton of `ester-clean-code` already contains living zones for quarantine, challenge windows, evidence handling, privilege guards, integrity, and persistent memory, so the new stack no longer needs only a conceptual bridge. It now has a credible code-anatomical landing map.**

---

## 15. Hidden bridges

### Hidden Bridge 1 — Cybernetics
The dump shows multiple negative-feedback surfaces already in place:
guarding, quarantine, rollback, windows, integrity checks.

### Hidden Bridge 2 — Information Theory
The repository already prefers compact typed records over narrative excess:
JSON state, windows, hashes, witness packets, route-level status responses.

---

## 16. Earth paragraph

In a real workshop, if you want to retrofit a new safety system into a machine, you do not begin by replacing the front panel. You first find the overload relay, the emergency stop chain, the maintenance lock, the inspection seal, and the fault log. This dump finally shows where those parts are in `ester-clean-code`. That is what makes the next step real.

---

## 17. Final position

This document marks the transition from abstract bridge-building to actual code anatomy.

The stack is no longer hovering above the repository.

It now has:
- runtime nerves,
- memory organs,
- guard surfaces,
- integrity tissue,
- and documentary bones
that can support the next phase.

The next serious move is not another concept note.

It is targeted file-level excavation.
