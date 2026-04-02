# File Excavation Notes — Batch A v0.1

**Status:** Targeted excavation notes  
**Scope:** First surgical batch for `ester-clean-code` public skeleton  
**Goal:** Move from abstract bridge language to file-level integration discipline for the new stack

**Batch A Files / Zones**
1. `modules/runtime/drift_quarantine.py`
2. `modules/runtime/comm_window.py`
3. `memory_manager.py`
4. `routes_memory.py` + `routes_mem.py`
5. `middleware/caution_guard.py`
6. `middleware/integrity_guard.py`
7. `middleware/rbac.py`
8. `app_plugins/ester_will_unified_guard.py`
9. `docs/iter47`–`iter51` as doctrinal bundle

---

## 1. Ground Rule for Batch A

Batch A is not the place to add cinematic beauty.

Batch A is where we protect and sharpen the existing:
- runtime collision discipline,
- quarantine discipline,
- challenge windows,
- evidence accountability,
- privilege boundaries,
- and memory separation.

Everything visually persuasive must wait.

The first obligation is to preserve:
**fail-closed reality over attractive continuity.**

---

## 2. File 1 — `modules/runtime/drift_quarantine.py`

## 2.1 What this file already is

This is the strongest existing anatomical candidate for the future core of:

- `GlitchNode`
- `ChallengeRecord`
- `Review / clear` mechanics
- expiry logic
- evidence-backed reopening
- rollback-to-safe-slot behavior

It already contains:
- state defaults
- challenge timestamps
- challenge deadlines
- expiry markers
- clear metadata
- evidence metadata
- L4W-related metadata
- failure streak / forced rollback logic
- status builder
- evidence packet verification
- explicit `clear_quarantine(...)`

This file is not a side utility.
It is already a proto-governance organ.

## 2.2 What must be preserved

Preserve these qualities exactly:

- **stateful quarantine row discipline**
- **append-only event mindset**
- **challenge window fields**
- **evidence-first clear path**
- **slot-aware enforce/observe split**
- **rollback-to-A under repeated verifier failures**

Do not flatten this into generic “errors.”

This file is valuable precisely because it already treats dangerous transitions as **procedural state**, not as mere exceptions.

## 2.3 What should be added later

Future insertion points here:

### A. `GlitchNode` typing
Right now the file already carries most of the fields needed for a typed runtime collision object.

Do not replace the quarantine row.
Instead add a more explicit typed view over the existing row shape.

Suggested future relation:
- quarantine row = runtime truth
- `GlitchNode` = graph/read model projection of that truth

### B. `ChallengeRecord`
Do not bury challenge events only inside row fields.
Introduce explicit first-class challenge records that reference:
- `agent_id`
- `event_id`
- challenge reason
- challenger role
- deadline
- review outcome ref

### C. `ReviewRecord`
Keep `clear_quarantine(...)` as a runtime operation.
But add a review object above it so “clear” becomes one possible review outcome, not the entire review vocabulary.

### D. `ResearchNode` emission
When a quarantine persists or expires, there should later be an optional controlled path that emits:
- a quarantined research object,
- not an executable continuation.

## 2.4 What must NOT be done here

Do not:
- rewrite this file into UI language,
- mix graph rendering concerns into runtime state,
- allow clear without evidence in enforced mode,
- remove historical fields in favor of a “cleaner” model,
- hide rollback-to-A because it feels inelegant.

Elegance that removes safety lineage is fake elegance.

## 2.5 First tests to add in the future

- quarantine set -> challenge window populated
- quarantine expire -> one-time expired event only
- clear with wrong event_id -> denied
- clear with bad evidence hash -> denied
- clear with valid evidence but broken L4W chain -> denied
- repeated verifier failures -> force Slot A
- historical row survives reinterpretation

## 2.6 Verdict

**Keep. Deepen. Do not re-center.**  
This file is already the living seed of the runtime half of the new stack.

---

## 3. File 2 — `modules/runtime/comm_window.py`

## 3.1 What this file already is

A clean bounded window primitive:
- open
- inspect
- close
- list
- persistent state
- TTL
- host allowlists
- reason fields

This is not “about messaging only.”
Architecturally, it is already a generic temporal gate.

## 3.2 What must be preserved

Preserve:
- explicit TTL
- explicit open/close
- persistent JSON state
- reason annotation
- small surface area

Its value is its minimality.

## 3.3 What should be added later

### A. Generalize only by naming, not by complication
Possible future reuse:
- challenge windows
- review windows
- privileged escalation windows
- temporary evidence inspection windows

But the right move is not to bloat it immediately.
Keep the primitive small.

### B. Separate kinds clearly
Use `kind` carefully:
- `telegram`
- `challenge_review`
- `evidence_inspect`
- `manual_clear`
- etc.

### C. Add optional witness refs later
Not now, but later a window may point to:
- `witness_ref`
- `challenge_ref`
- `review_ref`

without ceasing to be a simple time-box primitive.

## 3.4 What must NOT be done here

Do not turn this into:
- a generic workflow engine,
- a challenge resolution engine,
- or a runtime authority broker.

It should remain:
**a bounded permission window primitive.**

## 3.5 Verdict

**Preserve as a primitive. Reuse by composition, not by inflation.**

---

## 4. File 3 — `memory_manager.py`

## 4.1 What this file already is

This is the coordination organ for layered memory:
- short-term
- medium-term
- long-term/vstore
- flashback
- aliasing
- compaction
- meta-memory
- offers / agenda traces

It already has the shape of a memory orchestrator rather than a dumb store wrapper.

## 4.2 What must be preserved

Preserve:
- memory layer separation
- compatibility discipline
- flashback as explicit query path
- compaction as deliberate maintenance
- medium/long-term distinction

Do not make memory “simpler” by collapsing these layers.

## 4.3 What should be added later

### A. `ResearchNode` lane
This file is the likely place where research memory must become a first-class lane.

Not mixed into:
- normal long-term memory
- default flashback
- or ordinary retrieval

Suggested future idea:
- `research_lane`
- `quarantine_lane`
- `runtime_lane`
- `witness_lane`

### B. Retrieval discipline
Add explicit policy so speculative or quarantined objects do not leak into runtime synthesis unless:
- read mode says so,
- or explicit inspection path asks for them.

### C. Reopenability metadata
A `ResearchNode` stored through memory should later keep:
- reopenable / not reopenable
- required evidence
- source glitch ref
- evidence standing
- review status

## 4.4 What must NOT be done here

Do not:
- let graph needs distort memory semantics too early,
- allow flashback to become a speculative soup,
- store research artifacts in the same undifferentiated pool as trustworthy runtime history.

That path recreates hallucinated future continuity at the memory layer.

## 4.5 Verdict

**This is the future home of disciplined research memory — but only if lane separation stays sharp.**

---

## 5. File 4 — `routes_memory.py` + `routes_mem.py`

## 5.1 What these files already are

These are memory read/write surfaces for:
- flashback
- stats
- alias
- compact

They already provide stable human/API entrypoints over the memory manager.

## 5.2 What must be preserved

Preserve:
- small, explicit route semantics
- predictable errors
- compatibility handling
- separation between API and storage logic

These routes are valuable because they are boring in the right way.

## 5.3 What should be added later

### A. Read-only research inspection endpoints
Future candidates:
- `/memory/research/list`
- `/memory/research/item`
- `/memory/research/reopenability`
- `/memory/research/by_glitch`

### B. Explicit mode separation
Normal runtime memory routes should not silently include quarantined speculative nodes.

Possible future mode flags:
- `runtime_only`
- `research_only`
- `audit_view`
- `historical_expired`

### C. Graph read support
Later, graph-facing read models may pull from these routes or parallel services.
But not before typed state exists.

## 5.4 What must NOT be done here

Do not turn these routes into:
- challenge resolution endpoints,
- direct execution control,
- or graph mutation endpoints.

They should remain:
**memory-facing read/control surfaces, not governance engines.**

## 5.5 Verdict

**Extend later for read-side research visibility, but keep them boring and typed.**

---

## 6. File 5 — `middleware/caution_guard.py`

## 6.1 What this file already is

A global policy guard that:
- loads policy,
- matches risk rules,
- checks for consent pill,
- logs decision into an audit chain,
- supports A/B behavior.

This file already acts like a route-level “are you sure / are you allowed / do you have pill” layer.

## 6.2 What must be preserved

Preserve:
- explicit policy lookup
- explicit reason reporting
- explicit block/allow result
- audit-chain append
- A/B mode split

## 6.3 What should be added later

### A. Typed collision emission
Right now a block is a decision.
Later, a blocked request should also be able to emit a typed runtime collision view:
- `PrivilegeLock`
- `ConsentLock`
- `CautionLock`

This does **not** mean the middleware should become graph-aware.
It means runtime block events should become available for later projection into `GlitchNode`.

### B. Better relation to witness
If a dangerous action was denied:
- the denial itself may become witnessable,
- especially when later review disputes why it was denied.

### C. Reviewability hooks
Not direct review resolution here.
But enough metadata so a later challenge layer can say:
- what rule matched,
- what pill was missing,
- what decision reason was recorded.

## 6.4 What must NOT be done here

Do not:
- make this middleware the master of all challenge logic,
- mix it with graph rendering,
- or weaken the audit append behavior for convenience.

## 6.5 Verdict

**Keep as route-level risk gate. Later expose typed lock metadata outward.**

---

## 7. File 6 — `middleware/integrity_guard.py`

## 7.1 What this file already is

A narrow module-registration integrity gate:
- checks `.sig.json`
- verifies signature
- denies `/app/discover/register` when integrity fails
- has A/B and enforce behavior

This is exactly the kind of narrow ingress discipline one wants.

## 7.2 What must be preserved

Preserve:
- narrow focus
- signature-based decision
- explicit violations
- pre-execution denial

## 7.3 What should be added later

### A. Treat denials as typed integrity locks
Future runtime projection can map these denials into:
- `IntegrityLock`
- `SignatureMissingLock`
- `SignatureMismatchLock`

### B. Make it evidence-visible, not authority-generating
A successful integrity check proves admissibility at that boundary.
It must not be treated as:
- general legitimacy
- or broad truth.

### C. Possible witness relation
Registration denial or allow may later be worth recording with a witness envelope in strict modes.

## 7.4 What must NOT be done here

Do not broaden this into:
- generic policy engine
- or UI-driven approval mechanism.

Its value is that it is a hard, boring checkpoint.

## 7.5 Verdict

**Strong narrow ingress organ. Keep it narrow. Surface typed integrity outcomes later.**

---

## 8. File 7 — `middleware/rbac.py`

## 8.1 What this file already is

A very simple role model:
- persistent local role DB
- subject extraction
- minimum-role check
- bootstrap secret

It is intentionally small.

## 8.2 What must be preserved

Preserve:
- minimality
- local persistence
- explicit role ordering
- no magical role inference

## 8.3 What should be added later

### A. Distinguish role from evidence
This file should remain the role layer.
Do not push witness semantics into it.

### B. Possible future relation to review permissions
It may later answer:
- who may open a challenge
- who may review
- who may settle

But that should be done through role interpretation elsewhere, not by bloating this file.

### C. Subject clarity
If future graph/review systems rely on subject identity,
this file becomes an input source, not the full governance layer.

## 8.4 What must NOT be done here

Do not turn RBAC into:
- a challenge engine
- an evidence verifier
- or a volition replacement

## 8.5 Verdict

**Keep minimal. Use as a subject/role source, not as the whole policy brain.**

---

## 9. File 8 — `app_plugins/ester_will_unified_guard.py`

## 9.1 What this file already is

This is one of the most promising control surfaces in Batch A.

It already:
- maps sensitive HTTP paths to scopes and min levels
- constructs `VolitionContext`
- calls a default gate
- returns structured denial in Slot B
- keeps path-prefix sensitivity as explicit configuration

This is close to the nervous junction between:
- route action
- volition
- and bounded refusal

## 9.2 What must be preserved

Preserve:
- path -> scope -> level mapping
- explicit `VolitionContext`
- gate decision object semantics
- Slot-aware refusal
- route-local discipline

## 9.3 What should be added later

### A. Runtime lock projection
When this layer denies, future projection should be able to classify the outcome as:
- `VolitionLock`
- `PrivilegeLock`
- `NeedScopeLock`
- `MinLevelLock`

### B. Bridge to `GlitchNode`
This is a prime candidate for a later adapter:
- not the creator of graph nodes directly,
- but a source of typed refusal events for graph/read models.

### C. Review hooks
A later challenge layer may need:
- the exact `reason_code`
- slot
- route
- scopes requested
- level required
- metadata used in the volition decision

This file already comes close to providing the right anatomy.

## 9.4 What must NOT be done here

Do not:
- make this plugin manage challenge state itself
- or let it bypass lower physical/runtime locks.

Volition refusal is one kind of boundary.
It must not swallow the rest of L4.

## 9.5 Verdict

**High-value junction file. Probably the cleanest future source of typed route-level lock events.**

---

## 10. File 9 — `docs/iter47`–`iter51` bundle

## 10.1 What this bundle already is

This is not decoration.
This is the doctrinal backbone of the exact territory we are excavating.

The sequence already establishes:

- Iter47 — drift quarantine
- Iter48 — challenge window
- Iter49 — evidence packet required for clear
- Iter50 — integrity stack
- Iter51 — L4 witness envelope

That is an extraordinary amount of prior structure.

## 10.2 What must be preserved

Preserve:
- the iteration sequence itself
- the escalation of accountability
- the move from runtime block -> timed challenge -> evidence packet -> integrity stack -> L4 witness envelope

This progression is already architecturally meaningful.
Do not collapse it into one “unified security doc.”

## 10.3 What should be added later

### A. New companion note
A future doc should probably connect these iterations directly to:
- `GlitchNode`
- `ResearchNode`
- graph evidence notation
- challenge/review protocol
- status algebra

### B. Explicit anti-hallucination-of-future note
The current doctrinal bundle is already solving a real disease:
manual or aesthetic future claims bypassing evidence and runtime collision.

That should be named more openly in a future connective note.

## 10.4 Verdict

**Treat this as doctrine, not historical clutter. It is already the hidden spine of the new stack.**

---

## 11. Batch A synthesis

Batch A shows a very clear pattern:

- `drift_quarantine.py` -> runtime collision, challenge timing, evidence clear, expiry
- `comm_window.py` -> bounded temporal gate primitive
- `memory_manager.py` + memory routes -> future research lane and retrieval discipline
- `caution_guard.py` -> policy/risk lock surface
- `integrity_guard.py` -> narrow signed-ingress lock surface
- `rbac.py` -> subject/role source
- `ester_will_unified_guard.py` -> volitional route-level refusal surface
- `iter47–51` -> already-written doctrine of quarantine -> evidence -> integrity -> witness

This is not random.

The codebase already has the bones for the new stack.

What it does not yet have everywhere is:
- explicit shared naming,
- typed status algebra,
- first-class research memory objects,
- unified graph-facing read projections.

That is the next task.

---

## 12. Recommended next concrete move after Batch A

After Batch A, the cleanest next step is not another broad concept note.

It is:

**File Excavation Notes — Batch B**
focused on:
- `modules/memory/chroma_adapter.py` (once isolated)
- `validator/*`
- `rules/*`
- `merkle/*`
- `app_plugins/ester_thinking_trace_http.py`
- `app_plugins/ester_memory_flow_http.py`

That batch would complete the bridge from:
- runtime state
- to typed memory
- to evidence integrity
- to read-only graph visibility

---

## 13. Explicit bridge

The explicit bridge for Batch A is this:

**the first files that matter most are not UI files and not orchestration glamour files. They are the files where Ester already learned how to say “stop,” “not yet,” “show me evidence,” “your window expired,” and “I remember that this was disputed.”**

That is exactly where accountable continuity begins.

---

## 14. Hidden bridges

### Hidden Bridge 1 — Cybernetics
Batch A is almost entirely composed of negative-feedback organs:
refusal, quarantine, expiry, windows, integrity checks, role limits.

### Hidden Bridge 2 — Information Theory
Batch A already prefers compact typed state over rhetorical smoothing:
hashes, deadlines, booleans, event ids, reason codes, signatures.

---

## 15. Earth paragraph

In a real machine, the smartest part is often not the motor but the set of relays that cut power, the seals that show tampering, the maintenance logs, and the keys that prevent the wrong person from opening the panel. Batch A is that layer. If you misunderstand it as “just plumbing,” you end up building a beautiful interface over a machine that no longer knows how to refuse.

---

## 16. Final position

Batch A confirms something important:

The public skeleton of `ester-clean-code` already contains the beginnings of a disciplined immune system.

Not the whole organism.
Not the whole graph.
Not the whole future stack.

But the immune system is there.

That is why the bridge is now real.
