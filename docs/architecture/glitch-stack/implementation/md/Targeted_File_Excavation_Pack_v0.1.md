# Targeted File Excavation Pack v0.1

**Status:** Surgical reading pack  
**Scope:** Public `ester-clean-code` skeleton only (GitHub-visible dump, not private production Ester)  
**Purpose:** Move from file-map to file-level excavation priorities, attachment strategy, and “do not touch blindly” guidance.

---

## 1. Why this pack exists

The previous bridge and anatomy documents identified **where** the new stack can land.

This pack goes one level deeper.

It answers:

- which files already contain the nearest living analogues,
- what each file is already doing,
- what concept from the new stack belongs there first,
- what should **not** be forced into that file,
- and what order of excavation is the safest.

This is not a rewrite plan.  
It is a **surgical reading-and-attachment plan**.

---

## 2. Excavation order

### Tier A — read first, because they already contain living primitives

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

### Tier B — read immediately after, because they explain or support the same tissue

11. `routes/admin_keys.py`
12. `docs/iter47_drift_quarantine.md`
13. `docs/iter48_quarantine_challenge_window.md`
14. `docs/iter49_clear_requires_evidence_packet.md`
15. `docs/iter50_integrity_stack.md`
16. `docs/iter51_l4w_envelope.md`

### Tier C — defer until statuses and evidence become explicit

17. `app_plugins/ester_thinking_trace_http.py`
18. `app_plugins/ester_memory_flow_http.py`
19. `listeners/sidecar_orchestrator.py`
20. graph/UI/templates routes

---

## 3. File-by-file excavation

## 3.1 `modules/runtime/drift_quarantine.py`

### Why it matters
This is the most important file in the current pack.

Even from the dump slice alone, it already contains:

- `challenge_open_ts`
- `challenge_deadline_ts`
- `challenge_sec`
- `expired`
- `expired_ts`
- `expired_event_id`
- `cleared`
- evidence fields
- signature flags
- L4W envelope references
- rollback-to-A logic
- fail streak tracking
- forced mode tracking
- evidence path resolution

It already behaves like a proto-composite of:

- `GlitchNode`
- `WitnessState`
- `ChallengeRecord`
- cleared/expired status memory
- bounded review window discipline

### What to extract first
1. the state row schema
2. the event append path
3. the normalization logic
4. rollback / fail-closed triggers
5. evidence packet structure
6. challenge expiry rules

### What concept belongs here first
**`GlitchNode` family and challenge-bearing runtime collision state**

### What NOT to force here yet
- cinematic rendering logic
- broad UI concerns
- graph decoration
- speculative research retrieval UX

This file should remain close to runtime truth and quarantine truth.

### Likely future refactor direction
Split conceptually into:
- runtime collision emission
- quarantine state model
- challenge/review lifecycle
- evidence attachment normalization

Not necessarily into separate files immediately — but at least into clearly named internal sections.

---

## 3.2 `modules/runtime/comm_window.py`

### Why it matters
This file is small, clean, and conceptually powerful.

It already implements:

- `open_window`
- `is_open`
- `close_window`
- `list_windows`

with:
- TTL
- reason
- host allowlist
- expiry cleanup
- persistent JSON state

### What to extract first
1. window schema
2. cleanup semantics
3. persistence semantics
4. TTL default logic
5. close-vs-expire distinction

### What concept belongs here first
**time-bounded challenge and review windows**

This file is the strongest precedent for:
- challenge window objects
- review expiry
- bounded temporary rights
- maintenance / exception windows

### What NOT to force here yet
- full challenge meaning
- witness packet parsing
- branch semantics
- graph roles

Keep it a clean time-window primitive.

### Likely future refactor direction
Generalize from “comm window” toward:
- reusable bounded window primitive
- challenge window
- review window
- escalation window
without losing simplicity.

---

## 3.3 `modules/memory/chroma_adapter.py`

### Why it matters
The dump shows a very relevant memory adapter:

- hardening around env expansion
- auto-location of richest Chroma store
- `ChromaUI`
- status/search/list_recent/add_record/delete

### What to extract first
1. collection naming assumptions
2. current metadata model
3. whether object typing already exists
4. retrieval sort rules
5. add/search path shape
6. how much room there is for quarantine-specific filtering

### What concept belongs here first
**storage and retrieval discipline for `ResearchNode` and graph-facing read models**

### What NOT to force here yet
- review authority
- runtime legality
- graph semantics directly in Chroma

This layer should store and retrieve typed semantic objects, not decide what is executable.

### Likely future refactor direction
Add a typed storage profile for:
- `ResearchNode`
- `BackwardNode`
- evidence-linked semantic traces
- reopenability flags
- exclusion-from-runtime retrieval markers

---

## 3.4 `memory_manager.py`

### Why it matters
This is likely the central non-UI organ for:
- short-term
- medium-term
- flashback
- compaction
- aliasing
- memory maintenance

### What to extract first
1. current object model
2. existing memory classes
3. any separation between operational and reflective memory
4. compaction rules
5. session/meta memory
6. whether aliasing already creates lineage semantics

### What concept belongs here first
**`ResearchNode` persistence and quarantine memory channel**

### What NOT to force here yet
- direct witness cryptography
- graph rendering state
- UI badges

### Likely future refactor direction
Introduce a memory class that is:
- persistent
- queryable
- non-executable by default
- evidence-linkable
- challengeable
- reopenable only through guards

---

## 3.5 `routes_memory.py`

### Why it matters
This file exposes stable route-level memory primitives:

- `/flashback`
- `/stats`
- `/alias`
- `/compact`

with compatibility-aware calling into different memory manager shapes.

### What to extract first
1. route contracts
2. current response shapes
3. extension strategy
4. whether new read-only endpoints can be added without contract breakage

### What concept belongs here first
**safe read APIs for quarantined research and branch inspection**

### What NOT to force here yet
- action authority
- reopening logic
- challenge resolution decisions

Routes should expose state, not mutate legitimacy by convenience.

---

## 3.6 `routes_mem.py`

### Why it matters
This is a second lighter memory surface.
It may be useful as:
- compatibility bridge
- operator shortcut layer
- small-scope introspection API

### What to extract first
1. overlap vs `routes_memory.py`
2. whether one of the two should remain canonical
3. where new read endpoints would cause less confusion

### What concept belongs here first
**minimal inspection endpoints for graph/introspection mode**

### What NOT to force here yet
Do not split logic between too many competing memory route surfaces.

---

## 3.7 `middleware/rbac.py`

### Why it matters
Even before reading internals, this is the obvious entrypoint for:
- privilege lock
- role-bound refusal
- deny-by-default authority discipline

### What to extract first
1. current subject model
2. role mapping
3. denied path shape
4. whether refusals are typed or only textual
5. where refusal events can emit structured runtime collision objects

### What concept belongs here first
**`PrivilegeLock` as a typed `GlitchNode` source**

### What NOT to force here yet
- witness packet construction inside RBAC itself
- challenge UI
- research semantics

RBAC should deny and emit a typed event, not become a policy novel.

---

## 3.8 `middleware/caution_guard.py`

### Why it matters
This is a likely runtime refusal / hold-back surface.
It probably already embodies:
- “not now”
- “unsafe to proceed”
- cautionary stop behavior

### What to extract first
1. what triggers it
2. how it reports denial
3. whether there are existing reason codes
4. whether it already distinguishes safe-stop vs soft stop

### What concept belongs here first
**`CautionLock` / `SafetyLock` as a typed L4 collision source**

### What NOT to force here yet
Do not let this layer perform research transformation directly.
It should stop and classify, not narrativize.

---

## 3.9 `middleware/integrity_guard.py`

### Why it matters
This is likely where tamper suspicion, mismatch, or structural refusal already lives.

### What to extract first
1. current integrity checks
2. output shape on failure
3. whether failures are hash-based / structural / path-based
4. where these can emit evidence-linked events

### What concept belongs here first
**`IntegrityLock` and evidence downgrade / dispute triggers**

### What NOT to force here yet
Do not mix integrity refusal with privilege or research semantics without typing them separately.

---

## 3.10 `app_plugins/ester_will_unified_guard.py`

### Why it matters
By name alone, this looks like one of the most sensitive files in the public skeleton.

It likely touches:
- volition
- unified refusal
- route-level behavior governance
- anti-bypass logic

### What to extract first
1. what “will” means in code terms here
2. how unified guard is called
3. how refusal is surfaced
4. whether there are already reason codes or stateful refusals
5. whether this file is policy-only or runtime-adjacent

### What concept belongs here first
**the clean separation between authority-bearing intent and quarantined desire**

This is likely where the conceptual difference between:
- “wanted to”
- “allowed to”
- “could under L4”
must eventually become explicit.

### What NOT to force here yet
Do not dump all triad logic into this file just because its name sounds central.

This file is probably a boundary nerve, not the whole organ system.

---

## 3.11 `routes/admin_keys.py`

### Why it matters
The dump confirms this route already manages:
- key init
- public key load
- sign test
- verify test
- local-only trust handling

### What to extract first
1. current key storage assumptions
2. signing abstraction
3. verification abstraction
4. where evidence envelopes could hook in later

### What concept belongs here first
**witness/review signature support and evidence verification tooling**

### What NOT to force here yet
Do not turn admin keys into a graph UI.
Keep it cryptographic utility and trust surface.

---

## 3.12 docs `iter47`–`iter51`

### Why they matter
These docs are not side notes.
They are likely the best human-readable explanation of the code tissue we are about to touch:

- drift quarantine
- challenge window
- evidence packet requirement
- integrity stack
- L4W envelope

### What to extract first
1. intended lifecycle
2. naming discipline already used
3. where your current code vocabulary already overlaps the new concept vocabulary
4. where renaming would be unnecessary and harmful

### What concept belongs here first
**semantic alignment before code refactor**

### What NOT to force here yet
Do not rename working concepts just to match the new conceptual documents if the old names are already good enough and already public.

---

## 4. First concrete attachment proposals

## 4.1 `GlitchNode`
First attach here:
- `drift_quarantine.py`
- plus typed emissions from:
  - `rbac.py`
  - `caution_guard.py`
  - `integrity_guard.py`

Rule:
runtime and middleware create `GlitchNode`;
UI only renders it.

---

## 4.2 `ResearchNode / BackwardNode`
First attach here:
- `memory_manager.py`
- `chroma_adapter.py`

Rule:
quarantine memory stores it;
runtime never executes it directly.

---

## 4.3 `WitnessState`
First attach here:
- `drift_quarantine.py`
- `admin_keys.py`
- integrity / merkle layer second

Rule:
witness is evidence class, not authority.

---

## 4.4 `ChallengeRecord / ReviewRecord`
First attach here:
- `drift_quarantine.py`
- `comm_window.py`

Rule:
challenge lifecycle should reuse bounded window mechanics rather than invent a second incompatible timing system.

---

## 4.5 `StatusTuple / TransitionGuard`
First attach here:
- `validator/`
- `rules/`
- tests

Rule:
do not let status algebra remain implicit in ad hoc dict mutations forever.

---

## 5. Files to treat carefully

These are **high-risk for premature contamination**:

### UI / templates / rendering
- `templates/*`
- graph-like views
- cinematic walkthrough surfaces

**Reason:** very easy to make the system look more coherent than it procedurally is.

### Orchestrators
- `listeners/sidecar_orchestrator.py`
- `hybrid_job_router.py`

**Reason:** if statuses are not typed first, orchestration will amplify ambiguity.

### High-level “will” logic
- `ester_will_unified_guard.py`

**Reason:** conceptually central, but easy to overload with responsibilities.

---

## 6. Minimal excavation methodology

For each target file, the excavation should answer the same six questions:

1. **What truth does this file currently own?**
2. **What state does it already persist or emit?**
3. **What guard or refusal already exists?**
4. **What concept from the new stack belongs here first?**
5. **What should remain outside this file?**
6. **What tests would prove the new attachment did not weaken fail-closed behavior?**

This keeps the excavation disciplined.

---

## 7. Proposed next artifact after this pack

The next useful document after this one would be:

**`File Excavation Notes — Batch A v0.1`**

That document would contain one page per file for the first 5–6 files:
- what is already there
- what to preserve
- what to add
- what to forbid
- what tests to write

In other words:
this current pack names the surgical targets;
the next pack opens the body.

---

## 8. Explicit bridge

The explicit bridge is now practical:

**the public skeleton already contains runtime quarantine, time-bounded windows, persistent memory surfaces, privilege guards, and local signing tools, so the triad stack and its successor layers can now be attached by file-level surgery rather than by speculative architecture alone.**

---

## 9. Hidden bridges

### Hidden Bridge 1 — Cybernetics
Negative feedback already exists in code:
quarantine, rollback, deny, expiry, hold-fire, bounded windows.

### Hidden Bridge 2 — Information Theory
The dump shows a preference for compact persistent records:
JSON state, hashes, envelopes, typed route responses.
That is exactly the right substrate for status algebra.

---

## 10. Earth paragraph

When retrofitting a serious machine, the first pass is not “make it beautiful.”
It is:
find the overload relay,
find the maintenance lock,
find the fault log,
find the seal,
find the stop button,
and find the timer that says when a dangerous exception expires.
This excavation pack is that first pass for `ester-clean-code`.

---

## 11. Final position

This is the first document in the bridge sequence that feels genuinely close to code.

Not because the code is already finished.
But because the anatomical targets are now clear enough that the next move is no longer broad architecture.

The next move is deliberate incision.
