# ARL Target File Map for ester-clean-code v0.1
## Targeted file map for implementing ARL inside the executable skeleton

**Status:** Draft v0.1  
**Layer:** Implementation-facing target map  
**Canonical normative source:** ARL package in `sovereign-entity-recursion`  
**Implementation target:** `ester-clean-code`  
**Input basis:** local dump / manifest of the clean skeleton  
**Author:** Ivan Kotov  
**Location:** Brussels  
**Year:** 2026  

---

## Abstract

This document defines the first targeted file map for implementing the **Arbitration / Review Layer (ARL)** in `ester-clean-code`.

It is not a promise that all required mechanics already exist in finished form.
It is a disciplined map of where ARL can attach with the least violence to the current skeleton.

The practical question is:

> If ARL needs freeze, review, witness binding, standing, precedence, and lawful re-entry discipline, which files already look like the right bones?

This file answers that question.

---

## 1. Honest framing

The dump confirms that `ester-clean-code` is not an empty toy skeleton.
It already contains:
- runtime quarantine logic,
- witness-oriented runtime structures,
- oracle approval windows,
- volition gating,
- RBAC and safety windows,
- proactivity execution paths,
- integrity / Merkle primitives,
- and earlier glitch-stack implementation notes.

This is important.

It means ARL does not need to be forced into a foreign body.
It already has anatomical landing zones.

At the same time, this is still a **target map**, not a final wiring diagram.

---

## 2. Mapping principle

The map below follows one rule:

**first wave = existing control points, not speculative architecture.**

That means:
- prefer already-living runtime boundaries,
- prefer existing ledgers / windows / witnesses,
- prefer explicit guard surfaces,
- prefer typed state transitions over UI theatre,
- and postpone pretty rendering until the state algebra is real.

---

## 3. Priority classes

### P0 — first-wave implementation targets
These are the files most likely to participate directly in the first ARL implementation wave.

### P1 — second-wave reinforcement targets
These are highly relevant files that strengthen the first wave, but do not need to carry the first cut.

### P2 — later-phase visibility / operator / rendering targets
These are useful only after state and witness discipline are real.

---

## 4. P0 target files

## 4.1 Runtime dispute / freeze / challenge core

### `modules/runtime/drift_quarantine.py`
**Role:** strongest existing anatomical candidate for ARL dispute-state handling.

**Why it matters:**
This file is already visibly aligned with:
- quarantine state,
- challenge deadlines,
- evidence signatures,
- witness requirements,
- rollback-to-A,
- fail streak handling,
- expiry and cleared mechanics,
- and drift classification.

**Best ARL use:**
- dispute state storage
- challenge / review lifecycle
- quarantine continuation
- deadlock persistence
- delayed release / expiry handling
- irreversible-loss marking hooks

**ARL concept fit:**  
`PRE_ADMISSIBILITY_HOLD` / `EVIDENTIARY_FREEZE` / `QUARANTINE` / `DEADLOCKED`

**Priority:** P0

---

### `modules/runtime/comm_window.py`
**Role:** precedent for explicit time-boxed control windows.

**Why it matters:**
This file already gives:
- `open_window(...)`
- `is_open(...)`
- `close_window(...)`
- `list_windows()`
- TTL
- persistent state
- explicit reasons and expiry

**Best ARL use:**
- review windows
- challenge windows
- appeal windows
- temporary authority windows

**ARL concept fit:**  
challenge / appeal / bounded review timing

**Priority:** P0

---

### `modules/runtime/oracle_requests.py`
**Role:** request / approval / persistence surface for bounded oracle access.

**Why it matters:**
The current oracle path already persists request objects and approval state in a durable directory.

**Best ARL use:**
- claim / request intake pattern for review assistance
- approval trace for remote witness use
- bounded escalation requests during review
- explicit actor / reason / TTL preservation

**ARL concept fit:**  
bounded external witness acquisition

**Priority:** P0

---

### `modules/runtime/oracle_window.py`
**Role:** operational gate for remote cognition and bounded external review assistance.

**Why it matters:**
This is already a real gate, not a fantasy.
It stores:
- current window state
- windows ledger
- calls ledger
- time-bound open / close behavior

**Best ARL use:**
- review-time oracle usage
- explicit “remote witness allowed now” lanes
- witnessable denial when oracle path is closed
- no-background-truth-vending discipline

**ARL concept fit:**  
remote witness / oracle assistance under strict windowing

**Priority:** P0

---

### `modules/runtime/l4w_witness.py`
**Role:** primary ARL witness-binding landing zone.

**Why it matters:**
This file already looks like the strongest runtime witness surface for:
- witness records
- chain continuity
- signing
- profile support
- audit state
- publication-oriented evidence handling

**Best ARL use:**
- dispute-opened event
- evidence-admitted / rejected events
- freeze-entered events
- privilege-freeze events
- outcome-issued events
- appeal events
- irreversible-loss events

**ARL concept fit:**  
witness binding / audit-ready dispute trace

**Priority:** P0

---

## 4.2 Standing / privilege / authority gates

### `modules/volition/volition_gate.py`
**Role:** primary gate for bounded action under context, needs, budgets, and actor metadata.

**Why it matters:**
This is already close to ARL logic because ARL is not only about opinion.
It is about whether a path is allowed to proceed under bounded conditions.

**Best ARL use:**
- standing-aware review context
- privileged-action blocking
- review-mode budget narrowing
- lawful execution path gating
- no silent continuation under dispute

**ARL concept fit:**  
standing / lawful action gate / fail-closed execution

**Priority:** P0

---

### `modules/thinking/actions_volition.py`
**Role:** adapter surface between action system and volition gate.

**Why it matters:**
Useful as a routing bridge where disputed actions can be downgraded, denied, or redirected into ARL review mode.

**Best ARL use:**
- redirect privileged actions into review path
- mark disputed action kinds
- attach dispute metadata to action attempts

**ARL concept fit:**  
action interception under dispute

**Priority:** P0

---

### `modules/security/rbac.py`
**Role:** live role / permission / route-level privilege boundary.

**Why it matters:**
This file already frames access as controlled, logged, and rank-aware.

**Best ARL use:**
- standing class enforcement
- reviewer role separation
- delegated reviewer scope
- privilege freeze support
- rejection of malformed or over-scoped claims

**ARL concept fit:**  
standing / privilege freeze / anti-silent escalation

**Priority:** P0

---

### `modules/security/safe_windows.py`
**Role:** supporting safety-window control surface.

**Why it matters:**
Natural candidate for controlled timing rules around privileged or sensitive operations.

**Best ARL use:**
- delayed re-entry
- time-boxed release conditions
- scheduled cooling windows
- “not now” enforcement

**ARL concept fit:**  
re-entry timing / cool-down discipline

**Priority:** P0

---

### `modules/middleware/hold_fire.py`
**Role:** explicit caution / stop surface in middleware layer.

**Why it matters:**
This is one of the cleanest places where ARL can become a runtime “do not proceed” condition instead of a note in prose.

**Best ARL use:**
- pre-admissibility hold
- soft block before full freeze
- anti-impulsive action refusal

**ARL concept fit:**  
`PRE_ADMISSIBILITY_HOLD`

**Priority:** P0

---

### `modules/middleware/integrity_guard.py`
**Role:** integrity-based refusal surface.

**Why it matters:**
This is the right kind of place for:
- evidence path refusal,
- witness-chain sanity enforcement,
- hash / lineage protection,
- and no-laundering refusal.

**Best ARL use:**
- reject orphaned evidence
- reject broken lineage
- block unlawful re-entry due to integrity break

**ARL concept fit:**  
admissibility / evidence-chain legality

**Priority:** P0

---

### `app_plugins/ester_will_unified_guard.py`
**Role:** likely central unifying surface where will, authority, refusal, and anti-bypass routing meet.

**Why it matters:**
Even by name, this looks like one of the strongest “bridge” insertion points between:
- volitional boundary,
- runtime permission,
- unified refusal,
- and anti-bypass logic.

**Best ARL use:**
- route incoming action toward ARL when dispute flag exists
- centralize no-silent-bypass behavior
- preserve one refusal voice across surfaces

**ARL concept fit:**  
unified refusal / anti-bypass bridge

**Priority:** P0

---

## 4.3 Proactivity and review task routing

### `modules/proactivity/executor.py`
**Role:** strong candidate for turning disputes into bounded executable review tasks.

**Why it matters:**
The executor already sits on:
- planner output
- queueing
- agent creation
- action invocation
- volition gating
- template routing

**Best ARL use:**
- spawn review tasks
- spawn evidence gathering tasks
- persist review plan ids
- route disputed initiatives into safe/non-safe review templates
- ensure review is queued instead of improvised

**ARL concept fit:**  
review orchestration / safe execution path

**Priority:** P0

---

### `modules/proactivity/planner_v1.py`
**Role:** deterministic, offline-first planning surface.

**Why it matters:**
This is useful because ARL first-wave implementation should prefer deterministic plans over generative hand-waving.

**Best ARL use:**
- generate dispute handling plans
- generate evidence collection plans
- generate quarantine artifact plans
- define safe minimal step bundles

**ARL concept fit:**  
deterministic review-plan generation

**Priority:** P0

---

### `modules/proactivity/state_store.py`
**Role:** durable queue / runtime status memory for initiative handling.

**Why it matters:**
A dispute review path must not vanish after one process tick.

**Best ARL use:**
- store dispute queue entries
- store plan ids
- store active review status
- mark done / deadlocked / denied / resolved
- keep runtime review state visible

**ARL concept fit:**  
dispute queue / review runtime memory

**Priority:** P0

---

### `modules/proactivity/template_bridge.py`
**Role:** deterministic initiative → template selection layer.

**Why it matters:**
This is exactly the kind of place where ARL can select different execution postures:
- planner-like
- reviewer-like
- oracle-assisted
- low-risk vs elevated

**Best ARL use:**
- choose review template for dispute class
- separate low-risk evidence handling from oracle-requiring cases
- keep first-wave ARL bounded and explicit

**ARL concept fit:**  
review template routing

**Priority:** P0

---

### `modules/proactivity/agent_create_approval.py`
**Role:** approval surface for agent creation / elevated proactivity.

**Why it matters:**
Useful where ARL review may require creation of a bounded temporary review agent or explicit approval for such action.

**Best ARL use:**
- review-agent creation approval
- bounded reviewer instantiation
- explicit operator approval trail for non-trivial review actors

**ARL concept fit:**  
review actor creation discipline

**Priority:** P0

---

## 4.4 Quarantine and local storage

### `modules/quarantine/storage.py`
**Role:** natural storage landing zone for isolated disputed artifacts or branch payloads.

**Why it matters:**
ARL needs a place where “not allowed back into flow yet” is not merely a boolean.

**Best ARL use:**
- store quarantined evidence bundles
- store branch snapshots
- preserve disputed artifacts outside normal execution path

**ARL concept fit:**  
quarantine storage

**Priority:** P0

---

### `modules/quarantine/scanners.py`
**Role:** scanning / inspection surface for quarantined material.

**Why it matters:**
This is where bounded inspection of disputed or suspect artifacts can happen without pretending they are already reintegrated.

**Best ARL use:**
- quarantine inspection
- pre-release checks
- contradiction scanning before re-entry

**ARL concept fit:**  
release-condition inspection

**Priority:** P0

---

## 5. P1 reinforcement targets

## 5.1 Integrity / Merkle substrate

### `merkle/cas.py`
### `merkle/merkle_tree.py`

**Role:** lower-level integrity substrate.

**Best ARL use:**
- evidence packet content addressing
- branch lineage preservation
- witness-chain or split-lineage support
- historical branch preservation

**Priority:** P1

---

## 5.2 Additional safety / network / will surfaces

### `modules/ester/net_will_policy.py`
**Role:** network-facing will and outbound behavior policy.

**Best ARL use:**
- deny-by-default under dispute
- no network-assisted re-entry without lawful basis
- stricter outbound restrictions in freeze mode

**Priority:** P1

---

### `modules/ops/window_ops.py`
### `modules/ops/window_watch.py`

**Role:** operational windowing and live watch surfaces.

**Best ARL use:**
- operator-facing review timing support
- live watch of review-sensitive UI/task contexts
- later-stage operator tooling around review windows

**Priority:** P1

---

### `modules/thinking/actions_guardian_policy.py`
**Role:** policy-side reasoning for guarded actions.

**Best ARL use:**
- reason-code enrichment
- pre-execution risk classification
- challenge / refusal routing

**Priority:** P1

---

## 5.3 Trace / read-only operator visibility

### `app_plugins/ester_thinking_trace_http.py`
### `app_plugins/ester_memory_flow_http.py`

**Role:** read-model surfaces.

**Best ARL use:**
- operator-facing visibility into dispute trace
- memory flow inspection for contested continuity
- evidence overlay readouts

**Priority:** P1

---

## 5.4 Existing docs that should shape implementation wording

### `docs/iter47_drift_quarantine.md`
### `docs/iter48_quarantine_challenge_window.md`
### `docs/iter49_clear_requires_evidence_packet.md`
### `docs/iter50_integrity_stack.md`
### `docs/iter51_l4w_envelope.md`
### `docs/iter52_l4w_conformance_and_audit_cli.md`

**Role:** already-grown implementation culture.

**Best ARL use:**
- keep vocabulary aligned with the repo’s own drift/quarantine/evidence language
- avoid inventing a second dialect
- reuse earlier mental models

**Priority:** P1, but conceptually very important

---

## 5.5 Existing glitch-stack implementation packs

### `docs/architecture/glitch-stack/implementation/md/Bridge_to_ester_clean_code_v0.1.md`
### `docs/architecture/glitch-stack/implementation/md/Code_Anatomy_Extraction_Targeted_File_Map_v0.1.md`
### related implementation packs in the same subtree

**Role:** earlier targeted implementation corpus.

**Best ARL use:**
- preserve style continuity
- preserve implementation package layout
- avoid duplicate anatomy excavation from scratch

**Priority:** P1

---

## 6. P2 later-phase targets

## 6.1 Orchestration layer

### `listeners/sidecar_orchestrator.py`
### `listeners/hybrid_job_router.py`
### `listeners/selfcare_scheduler.py`
### `judge_combiner.py`
### `group_intelligence.py`
### `group_digest.py`
### `daily_cycle.py`

**Role:** system-wide orchestration and coordination.

**Why later:**
These become relevant once ARL is no longer route-local and starts affecting wider long-lived scheduling behavior.

**Best ARL use later:**
- prevent blind relaunch of forbidden branches
- route unresolved disputes into safe queues
- coordinate longer-lived review / recovery cycles

**Priority:** P2

---

## 6.2 UI / rendering / route surfaces

### `templates/`
### `landing/`
### `docs/*.html`
### `ESTER/routes/*`
### `routes/*`

**Role:** operator/admin visibility and interface surfaces.

**Why later:**
The repo already has enough UI to become dangerously persuasive.
ARL should not become pretty before it becomes real.

**Best ARL use later:**
- review badges
- dispute overlay
- challenge markers
- operator audit readouts
- lawful re-entry status visibility

**Priority:** P2

---

## 7. Concept-to-file landing map

## 7.1 `Dispute`
Best first landing:
- `modules/proactivity/state_store.py`
- `modules/proactivity/executor.py`
- `modules/runtime/drift_quarantine.py`

## 7.2 `Standing`
Best first landing:
- `modules/security/rbac.py`
- `modules/volition/volition_gate.py`
- `app_plugins/ester_will_unified_guard.py`

## 7.3 `Evidence admissibility`
Best first landing:
- `modules/middleware/integrity_guard.py`
- `modules/runtime/l4w_witness.py`
- `merkle/cas.py`
- `merkle/merkle_tree.py`

## 7.4 `Freeze / hold`
Best first landing:
- `modules/middleware/hold_fire.py`
- `modules/runtime/drift_quarantine.py`
- `modules/security/safe_windows.py`

## 7.5 `Quarantine`
Best first landing:
- `modules/runtime/drift_quarantine.py`
- `modules/quarantine/storage.py`
- `modules/quarantine/scanners.py`

## 7.6 `Review window / challenge window`
Best first landing:
- `modules/runtime/comm_window.py`
- `modules/runtime/oracle_window.py`
- `modules/security/safe_windows.py`

## 7.7 `Witness binding`
Best first landing:
- `modules/runtime/l4w_witness.py`
- `modules/runtime/drift_quarantine.py`
- `merkle/*`

## 7.8 `Oracle-assisted bounded review`
Best first landing:
- `modules/runtime/oracle_requests.py`
- `modules/runtime/oracle_window.py`
- `modules/proactivity/template_bridge.py`

## 7.9 `Outcome / appeal / re-entry`
Best first landing:
- `modules/runtime/drift_quarantine.py`
- `modules/security/safe_windows.py`
- `modules/proactivity/state_store.py`

---

## 8. Strict first reading set

If the implementation work had to start immediately, the first full-read set should be:

1. `modules/runtime/drift_quarantine.py`
2. `modules/runtime/l4w_witness.py`
3. `modules/runtime/oracle_window.py`
4. `modules/runtime/oracle_requests.py`
5. `modules/volition/volition_gate.py`
6. `modules/security/rbac.py`
7. `modules/middleware/hold_fire.py`
8. `modules/middleware/integrity_guard.py`
9. `app_plugins/ester_will_unified_guard.py`
10. `modules/proactivity/executor.py`
11. `modules/proactivity/state_store.py`
12. `modules/proactivity/template_bridge.py`
13. `modules/quarantine/storage.py`
14. `modules/quarantine/scanners.py`
15. `docs/iter47_drift_quarantine.md`
16. `docs/iter48_quarantine_challenge_window.md`
17. `docs/iter49_clear_requires_evidence_packet.md`
18. `docs/iter51_l4w_envelope.md`

That is the real first wave.

---

## 9. What not to touch first

The following should **not** carry the first implementation wave:

- decorative UI pages
- large admin templates
- operator dashboards
- generalized orchestration code
- “smart Judge” synthesizers
- federation-wide sociality layers

If ARL starts as interface cosmetics or grand orchestration magic,
it will rot before it stabilizes.

---

## 10. Proposed next implementation documents after this file

This file should be followed by:

1. `ARL_Runtime_Hook_Points_v0.1.md`
2. `ARL_Minimal_Event_Types_for_ester_clean_code_v0.1.md`
3. `ARL_Dispute_State_Persistence_v0.1.md`
4. `ARL_Review_Task_Routing_v0.1.md`

That would move us from anatomy map to wiring plan.

---

## 11. Explicit bridge

**ARL normative layer ↔ ester-clean-code control points ↔ witness-bound executable discipline**

---

## 12. Hidden bridges

### 12.1 DEA / EA standing
Standing logic should remain linked to structured legitimacy, not dissolved into generic “request came in” handling.

### 12.2 SER-FED anti-capture
No single file or service in the implementation should quietly become the new king.
Bounded review remains bounded review.

---

## 13. Earth paragraph

On a real warehouse floor, you do not rebuild the whole building to enforce one dispute procedure. You identify the gate, the lock, the seal log, the quarantine bay, the supervisor clipboard, and the release stamp. This file map is exactly that for `ester-clean-code`: not a fantasy of total redesign, but a map of where the existing doors already are.
