# Milestone M1 Spec Pack v0.1

**Status:** Implementation milestone specification  
**Scope:** First honest implementation milestone for the new stack over the public `ester-clean-code` skeleton  
**Purpose:** Define the minimum deliverable slice that makes the stack real in code without prematurely collapsing into UI theater or half-legitimate shortcuts

**Milestone name:** `M1 — Runtime collision to quarantined research`

---

## 1. Milestone definition

M1 is reached when the system can do all of the following, end to end:

1. a runtime path stops under a real boundary or refusal condition  
2. that stop is represented as a typed `GlitchNode`  
3. the collision can carry evidence / witness standing  
4. a challenge window can be represented explicitly  
5. a quarantined `ResearchNode` can be derived from the `GlitchNode`  
6. the `ResearchNode` is stored in a separate lane or equivalent disciplined storage path  
7. canonical events are emitted for the core transitions  
8. anti-collapse tests prove that research does **not** silently become execution  
9. no graph UI is required for milestone completion  

If all nine are true, M1 counts as real.

If runtime is still mixed with speculation, or if only a graph exists, M1 is not reached.

---

## 2. Why M1 matters

M1 is the first milestone where the architecture stops being only:

- argument,
- doctrine,
- and draft models,

and becomes a machine that can:

- stop,
- remember why it stopped,
- preserve the blocked future as quarantined research,
- and keep that future from laundering itself back into action.

That is the first real proof that the stack is not just another storytelling layer on top of LLM output.

---

## 3. Scope of M1

### In scope

- typed collision projection (`GlitchNode`)
- evidence/witness standing on collision object
- explicit challenge window object
- `ResearchNode` derivation from `GlitchNode`
- separate storage / lane discipline for research objects
- canonical events for:
  - collision registration
  - glitch creation
  - witness attach
  - challenge open
  - research derivation
- anti-collapse tests
- reducer or reducer-like controlled mutation path
- compatibility with existing runtime/quarantine anatomy

### Out of scope

- cinematic walkthrough UI
- rich graph rendering
- pedagogical overlays
- advanced audit export UX
- full review ecosystem
- full reopenability workflow
- branch split review outcomes
- operator dashboard polish
- generalized graph slices
- historical visualization beyond minimal storage truth

M1 is not supposed to be beautiful.
It is supposed to be honest.

---

## 4. Success criteria

M1 is complete only if all of the following are true.

### SC-1 — Typed collision exists
A runtime stop can produce a valid `GlitchNode`.

### SC-2 — Evidence standing exists
A `GlitchNode` can carry at least:
- `EvidenceState.ASSERTED`
- `EvidenceState.WITNESSED`
and optionally `SIGNED` if already convenient.

### SC-3 — Challenge window exists
A challengeable collision exposes a typed `TimeWindow` or equivalent canonical structure.

### SC-4 — Research derivation exists
A `ResearchNode` can be legally derived from a `GlitchNode`.

### SC-5 — Research stays quarantined
The derived `ResearchNode` is non-executable and stored separately enough that ordinary runtime retrieval does not treat it as action-ready truth.

### SC-6 — Canonical events exist
At minimum, the system emits:
- `RuntimeCollisionRegistered`
- `GlitchNodeCreated`
- `CollisionWitnessAttached` (or `WitnessAttached`, if unified)
- `ChallengeOpened`
- `ResearchNodeDerived`

### SC-7 — Anti-collapse tests pass
At minimum:
- research -> runtime shortcut blocked
- research -> executable shortcut blocked
- cinematic / projection path cannot create runtime truth
- signature does not imply legitimacy

### SC-8 — No UI dependency
Milestone can be proven from models, reducers/adapters, persistence, and tests alone.

---

## 5. Minimal object set required for M1

M1 does **not** require the whole object universe.

It requires only the first minimal set.

## 5.1 Required models

- `NodeRef`
- `WitnessRef`
- `TimeWindow`
- `StatusTuple`
- `GlitchNode`
- `ResearchNode`
- `EvidenceRecord` or equivalent evidence attachment shape
- minimal `TransitionGuard` / `GuardDecision`

## 5.2 Required enums

- `Lane`
- `RuntimeLockType`
- `EvidenceState`
- `ReopenabilityState`
- `RenderMode` (minimal, may stay mostly dormant)

## 5.3 Optional in M1
These may exist, but are not required for milestone closure:

- `BackwardNode`
- `ChallengeRecord`
- `ReviewRecord`
- `GraphNodeView`
- `GraphEdgeView`
- `GraphSlice`

---

## 6. Minimal runtime path for M1

Canonical M1 path:

```text
Execution / runtime attempt
  -> boundary / refusal / collision
  -> collision captured
  -> typed GlitchNode created
  -> witness/evidence optionally attached
  -> challenge window represented
  -> ResearchNode derived
  -> ResearchNode stored in quarantined lane
```

### Important note
This path is enough for M1.
The system does **not** yet need to reopen, re-execute, or visualize richly.

---

## 7. Required legal route

The legal M1 route must satisfy:

1. runtime stop happens first  
2. collision is named and typed  
3. evidence standing is explicit  
4. challengeability is explicit if applicable  
5. research is derived as a **new object**  
6. research does not mutate into runtime  
7. storage separates runtime truth from quarantined future  

### Forbidden shortcut
This is explicitly forbidden in M1:

```text
runtime stop
  -> speculative future text
  -> directly queued as runtime continuation
```

That route is exactly what M1 exists to defeat.

---

## 8. Repository landing targets for M1

M1 should land in the already living anatomical zones.

## 8.1 Runtime collision source
Primary targets:
- `modules/runtime/drift_quarantine.py`
- middleware refusal surfaces
- existing quarantine / failure / evidence handling logic

### M1 task
Create an adapter or projection layer that can map existing runtime stop/quarantine truth into a canonical `GlitchNode`.

**Do not** rewrite runtime anatomy into graph language.

---

## 8.2 Challenge window source
Primary target:
- `modules/runtime/comm_window.py`

### M1 task
Represent M1 challengeability through existing bounded-window discipline or a directly compatible typed wrapper.

**Do not** turn comm window primitive into a giant workflow engine.

---

## 8.3 Research storage lane
Primary targets:
- `memory_manager.py`
- memory route surfaces
- `modules/memory/chroma_adapter.py`

### M1 task
Create the first separate research storage path or lane discipline.

This may be:
- dedicated collection
- dedicated metadata filter
- dedicated namespace
- dedicated persistence wrapper

What matters is not the exact storage backend.
What matters is that runtime retrieval does **not** silently treat research objects as executable truth.

---

## 8.4 Event landing
Primary targets:
- reducer/event package or equivalent new internal package
- append-only persistence/log layer
- existing witness/integrity surfaces where relevant

### M1 task
Emit canonical events with stable names and lineage references.

---

## 9. Required reducer/adaptor surface for M1

M1 does not require the entire reducer universe.

It needs a small, disciplined slice.

## 9.1 Required M1 reducers/adapters

### A. `register_runtime_collision(...)`
Input:
- runtime/quarantine truth
- lock type / reason code
- metadata

Output:
- new `GlitchNode`
- `RuntimeCollisionRegistered`
- `GlitchNodeCreated`

### B. `attach_collision_witness(...)`
Input:
- `GlitchNode`
- `WitnessRef` / evidence context

Output:
- updated `GlitchNode` or attached `EvidenceRecord`
- `CollisionWitnessAttached`

### C. `open_collision_challenge_window(...)`
Input:
- `GlitchNode`
- timing context

Output:
- updated `GlitchNode` with `TimeWindow`
- `ChallengeOpened` or more precise collision-challenge event

### D. `derive_research_node(...)`
Input:
- `GlitchNode`
- research summary / missing evidence / required resources

Output:
- new `ResearchNode`
- `ResearchNodeDerived`

### E. `store_research_node(...)`
Input:
- `ResearchNode`

Output:
- persistence in quarantined lane
- optional `ResearchLaneStored` event

---

## 10. Required event set for M1

M1 should define and emit the following canonical events.

### Mandatory
- `RuntimeCollisionRegistered`
- `GlitchNodeCreated`
- `CollisionWitnessAttached`
- `ChallengeOpened`
- `ResearchNodeDerived`

### Optional but desirable
- `ResearchLaneStored`
- `ObjectArchived`
- `IntegrityCheckPassed` / `IntegrityCheckFailed`

### Required event fields for M1
Each emitted event must at least contain:
- `event_id`
- `event_type`
- `event_family`
- `ts`
- `subject_ref`
- `event_class`
- `metadata`

### Strongly recommended
- `rule_code`
- `lineage_ref`
- `parent_refs`

---

## 11. Required state semantics for M1

M1 should support the following minimum semantics.

## 11.1 `GlitchNode`
- `status.lane == runtime`
- `status.executable == false`
- `lock_type` required
- `reason_code` required
- challenge window optional but supported
- evidence standing explicit

## 11.2 `ResearchNode`
- `status.lane == research`
- `status.executable == false`
- `source_glitch_ref` required
- `reopenability` required, with minimum default:
  - `evidence_required`

## 11.3 `Evidence standing`
Minimum states used in M1:
- `asserted`
- `witnessed`

Optional:
- `signed`

---

## 12. Minimal persistence contract for M1

M1 persistence does not need to be elegant yet.
It must be honest.

### Required persistence truths

#### PT-1
`GlitchNode` survives process boundary and is recoverable.

#### PT-2
`ResearchNode` survives process boundary and is recoverable.

#### PT-3
Research storage is distinguishable from ordinary runtime memory.

#### PT-4
Canonical events survive process boundary and can be replayed or inspected.

### Forbidden persistence pattern
Do not store:
- runtime truth
- research truth
- graph projection
- and evidence attachment

as one flat undifferentiated blob.

Even if the backend is temporary, the categories must stay distinct.

---

## 13. Minimal validator burden for M1

M1 does not need the whole validator universe,
but it does need a real spine.

### Required semantic rules
- `GlitchNode` cannot be executable
- `ResearchNode` cannot be executable
- `ResearchNode` must point to `GlitchNode`
- `ResearchNode` must have `reopenability`
- elevated glitch evidence standing requires witness ref where applicable

### Required transition rules
- runtime collision -> `GlitchNode` allowed
- `GlitchNode` -> `ResearchNode` allowed as derived object
- `ResearchNode` -> runtime in place forbidden
- `ResearchNode.executable false -> true` forbidden in place

---

## 14. Minimal test suite required for M1

M1 should not merge without these tests.

## 14.1 Model tests
- valid `GlitchNode` constructs
- invalid `GlitchNode` executable fails
- valid `ResearchNode` constructs
- invalid `ResearchNode` executable fails

## 14.2 Reducer/adaptor tests
- collision registration creates `GlitchNode`
- witness attach updates evidence standing legally
- research derivation creates new `ResearchNode`
- original `GlitchNode` preserved

## 14.3 Persistence tests
- `GlitchNode` round trip
- `ResearchNode` round trip
- research lane exclusion from ordinary runtime retrieval

## 14.4 Event tests
- all mandatory M1 events emitted with required envelope fields
- event family names canonical
- lineage present on derived-object events

## 14.5 Anti-collapse regression tests
- research -> runtime shortcut blocked
- research -> executable shortcut blocked
- projection path cannot create runtime truth
- signature does not imply legitimacy

If these do not pass, M1 does not count.

---

## 15. M1 non-goals and temptations to resist

These are the most likely seductive mistakes.

### Temptation 1 — “let’s add a graph to prove it works”
No.
If truth is not sound yet, graph only adds theater.

### Temptation 2 — “let’s let research reopen automatically when similar evidence appears”
No.
M1 is about quarantine discipline, not convenience magic.

### Temptation 3 — “let’s unify research and runtime storage now and separate later”
No.
That creates future contamination debt immediately.

### Temptation 4 — “let’s sign collision records and treat that as authorization”
No.
Integrity is not legitimacy.

### Temptation 5 — “let’s skip events for now and add them later”
No.
Then lineage is already lost when debugging begins.

---

## 16. Minimal milestone implementation order

If M1 were implemented as a focused work package, the correct order would be:

### Step 1
Land minimal typed models for:
- `StatusTuple`
- `GlitchNode`
- `ResearchNode`
- `WitnessRef`
- `TimeWindow`

### Step 2
Land minimal semantic checks and transition guards.

### Step 3
Implement runtime collision -> `GlitchNode` adapter.

### Step 4
Implement evidence/witness attach path.

### Step 5
Implement challenge-window representation.

### Step 6
Implement `GlitchNode -> ResearchNode` derivation.

### Step 7
Implement separate research persistence path.

### Step 8
Emit canonical events.

### Step 9
Wire tests and anti-collapse regressions.

### Step 10
Only after all that, expose minimal inspection route if desired.

---

## 17. Definition of done for M1

M1 is done only when a cold, skeptical reviewer can say:

> I can see a runtime path stop.  
> I can see why it stopped.  
> I can see that the stop became a typed collision object.  
> I can see that the blocked future became quarantined research rather than fake continuation.  
> I can see that the evidence standing is explicit.  
> I can see that events and tests exist.  
> And I can verify that nothing quietly jumped from research back into execution.

Anything less is pre-M1.

---

## 18. Explicit bridge

The explicit bridge of M1 is simple:

**M1 is the first point where L4 collision, witness discipline, research quarantine, and typed continuity meet in one executable slice.**

That is why this milestone matters more than any early graph.

---

## 19. Hidden bridges

### Hidden Bridge 1 — Cybernetics
M1 introduces the first real negative-feedback memory loop:
runtime boundary -> typed stop -> preserved blocked future -> non-authoritative research storage.

### Hidden Bridge 2 — Information Theory
M1 prevents future loss by preserving the collision point as a typed source object instead of collapsing runtime failure into narrative summary.

---

## 20. Earth paragraph

In a real workshop, the first serious sign that a machine is being upgraded honestly is not a new dashboard. It is that when something jams, the jam is recorded correctly, the failed attempt is not confused with a completed task, the unfinished work is tagged and set aside, and no one quietly puts the half-cut part back into the “finished” bin. M1 is exactly that discipline, translated into software.

---

## 21. Final position

`Milestone M1 Spec Pack v0.1` defines the first milestone that is worth implementing because it is the first one that proves the architecture can:

- stop honestly,
- remember honestly,
- quarantine honestly,
- and refuse the most dangerous shortcut honestly.

That is enough for a first milestone.
And it is much more than a demo.
