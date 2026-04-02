# Reducer / State Machine Draft Pack v0.1

**Status:** Draft execution-logic pack  
**Scope:** Reducer and state-machine layer for the first implementation phase of the new stack  
**Purpose:** Define how typed objects from the previous packs are allowed to evolve through commands, events, guards, and derived-object emission

**Builds on**
- `Object Model Draft Pack v0.1`
- `Schema Pack v0.1`
- `Semantic Validator Rules Pack v0.1`
- `Transition Legality Matrix Pack v0.1`
- `Pydantic Models Draft Pack v0.1`

---

## 1. Why this pack exists

The previous packs defined:

- what objects exist,
- what fields they carry,
- what they mean,
- and which transitions are legal.

That still leaves one crucial question:

**How should the system actually perform state change?**

If this question is not answered explicitly, implementation drifts toward:
- ad hoc mutation,
- UI-driven shortcuts,
- hidden side effects,
- and illegal “just update the object” logic.

This pack exists to prevent that.

It defines a reducer-oriented state machine style where:
- commands request change,
- guards decide legality,
- reducers apply legal state updates,
- and some transitions emit **new derived objects** instead of mutating old ones in place.

That distinction is central.

---

## 2. Core reducer principles

### 2.1 Reducers are boring on purpose
A reducer should not be “smart.”
It should be:
- deterministic,
- narrow,
- replayable,
- auditable,
- and easy to test.

### 2.2 Guards decide legality before mutation
Reducers do not invent permission.
They consume decisions already checked by:
- schema validation
- semantic validation
- transition legality
- integrity checks (when relevant)

### 2.3 Derived objects are preferable to dangerous in-place mutation
Some transitions must create a new object rather than rewrite the old one.

Examples:
- `ExecutionNode -> GlitchNode`
- `GlitchNode -> ResearchNode`
- `ResearchNode -> new runtime candidate`
- review split -> new branch object

### 2.4 Display state never drives runtime truth
No reducer should accept a `GraphNodeView` as an authoritative source of runtime mutation.

### 2.5 Fail-closed is default
If:
- guards fail,
- required evidence is absent,
- a reducer route is ambiguous,
- or lineage would be destroyed,

then:
- no partial mutation,
- no hidden downgrade,
- no “best effort” rewrite,
- no silent fallback to a prettier state.

---

## 3. State machine vocabulary

## 3.1 Commands

Commands express **intent to attempt** a state change.

Examples:
- `OpenChallenge`
- `StartReview`
- `ResolveReview`
- `ExpireChallenge`
- `RecordObservation`
- `AttachWitness`
- `SignEvidence`
- `ArchiveObject`
- `DeriveResearchNode`
- `DeriveBackwardNode`
- `RecastHistoricalToResearch`
- `CreateRuntimeCandidateFromResearch`

Commands are not truth.
They are requests.

---

## 3.2 Events

Events express **what actually happened** after guards and reducers accepted a route.

Examples:
- `ObservationRecorded`
- `WitnessAttached`
- `EvidenceSigned`
- `ChallengeOpened`
- `ChallengeQueued`
- `ReviewStarted`
- `ReviewResolvedModify`
- `ReviewResolvedSplit`
- `ChallengeExpired`
- `ResearchNodeDerived`
- `BackwardNodeDerived`
- `RuntimeCandidateCreated`
- `ObjectArchived`

Events are the durable record of legal transition outcomes.

---

## 3.3 Reducers

Reducers consume:
- current object(s)
- validated command
- guard outcome
- optional side-channel input already verified

and produce:
- updated object
- emitted event(s)
- optional derived object(s)

---

## 3.4 Guards

Guards answer:
- is this route legal?
- what conditions are still missing?
- what rule code governs the decision?

Guards must return machine-readable results.

---

## 4. Architectural shape

A future transition pipeline should look like:

```text
command
  -> schema validation
  -> semantic validation
  -> transition legality check
  -> integrity / witness / policy guards (if needed)
  -> reducer
  -> event emission
  -> optional derived object emission
  -> persistence
  -> read-model / graph projection refresh
```

Important:
- graph projection is last
- graph projection is derived
- graph projection is never permission source

---

## 5. Reducer families

The system should not have one giant reducer.

It should have several reducer families.

## 5.1 Evidence reducer family
Handles:
- `asserted -> observed`
- `observed -> witnessed`
- `witnessed -> signed`
- `signed/witnessed -> challenge_open`
- `challenge_open -> settled`
- `* -> expired`

## 5.2 Challenge reducer family
Handles:
- challenge open / queue / review / resolve / dismiss / expire / archive

## 5.3 Research reducer family
Handles:
- derive `ResearchNode`
- derive `BackwardNode`
- reopenability changes
- historical recast
- controlled candidate creation

## 5.4 Runtime collision reducer family
Handles:
- execution stop
- glitch creation
- archival of terminal runtime paths
- witness binding to collision objects

## 5.5 Graph/read reducer family
Strictly derived:
- create/update graph views
- create graph slices
- refresh evidence badges
- never mutate runtime truth

---

## 6. Canonical command objects

These may later be Pydantic models, dataclasses, or internal dict contracts.

## 6.1 `RecordObservationCommand`

```python
{
  "command": "RecordObservation",
  "target_evidence_id": "...",
  "observed_ts": 1775075000,
  "actor": "runtime_sensor",
  "metadata": {}
}
```

### Intended result
- `EvidenceRecord.evidence_state: asserted -> observed`

---

## 6.2 `AttachWitnessCommand`

```python
{
  "command": "AttachWitness",
  "target_ref": {"node_id": "glitch_01H...", "node_kind": "GlitchNode"},
  "witness_ref": {...},
  "actor": "system",
  "metadata": {}
}
```

### Intended result
- attach witness to target
- possibly elevate evidence state if legal

---

## 6.3 `SignEvidenceCommand`

```python
{
  "command": "SignEvidence",
  "evidence_id": "evid_01H...",
  "signer": "entity-key",
  "payload_hash": "....",
  "metadata": {}
}
```

### Intended result
- `EvidenceRecord.evidence_state: witnessed -> signed`

---

## 6.4 `OpenChallengeCommand`

```python
{
  "command": "OpenChallenge",
  "target_ref": {"node_id": "glitch_01H...", "node_kind": "GlitchNode"},
  "opened_by_role": "human_anchor",
  "opened_by_subject": "Owner",
  "reason": "classification dispute",
  "opened_ts": 1775075100,
  "deadline_ts": 1775078700,
  "metadata": {}
}
```

### Intended result
- new `ChallengeRecord`
- target evidence state may move to `challenge_open`

---

## 6.5 `StartReviewCommand`

```python
{
  "command": "StartReview",
  "challenge_id": "chg_01H...",
  "reviewer_role": "external_reviewer",
  "reviewer_subject": "Auditor",
  "started_ts": 1775075200,
  "metadata": {}
}
```

### Intended result
- challenge state `queued -> under_review`

---

## 6.6 `ResolveReviewCommand`

```python
{
  "command": "ResolveReview",
  "challenge_id": "chg_01H...",
  "reviewer_role": "external_reviewer",
  "reviewer_subject": "Auditor",
  "outcome": "reclassify",
  "previous_target_class": "DeadEndNode",
  "new_target_class": "ResearchNode",
  "signed": true,
  "witness_ref": {...},
  "notes": "recast under evidence constraints",
  "metadata": {}
}
```

### Intended result
- new `ReviewRecord`
- challenge resolved
- possibly derive new branch object
- historical lineage preserved

---

## 6.7 `ExpireChallengeCommand`

```python
{
  "command": "ExpireChallenge",
  "challenge_id": "chg_01H...",
  "expired_ts": 1775079000
}
```

### Intended result
- challenge state -> `expired`

---

## 6.8 `DeriveResearchNodeCommand`

```python
{
  "command": "DeriveResearchNode",
  "source_glitch_ref": {"node_id": "glitch_01H...", "node_kind": "GlitchNode"},
  "title": "Need explicit privilege proof",
  "summary": "Branch halted at privilege boundary.",
  "missing_evidence": ["signed escalation approval"],
  "required_resources": ["review"],
  "metadata": {}
}
```

### Intended result
- new `ResearchNode`
- no mutation of `GlitchNode` into research

---

## 6.9 `DeriveBackwardNodeCommand`

```python
{
  "command": "DeriveBackwardNode",
  "source_research_ref": {"node_id": "research_01H...", "node_kind": "ResearchNode"},
  "target_future_description": "successful branch continuation",
  "gap_statement": "runtime continuation blocked by privilege boundary",
  "required_evidence": ["approval token"],
  "bridge_assumptions": ["new role assignment possible"],
  "metadata": {}
}
```

### Intended result
- new `BackwardNode`

---

## 6.10 `CreateRuntimeCandidateFromResearchCommand`

```python
{
  "command": "CreateRuntimeCandidateFromResearch",
  "source_research_ref": {"node_id": "research_01H...", "node_kind": "ResearchNode"},
  "gate_ref": "gate_01H...",
  "actor": "system",
  "metadata": {}
}
```

### Intended result
- new `ExecutionNode` candidate or runtime attempt object
- **not** in-place mutation of `ResearchNode.status.executable`

---

## 7. Canonical event objects

Events should be small and factual.

## 7.1 Suggested shared event envelope

```python
{
  "event_id": "evt_01H...",
  "event_type": "ChallengeOpened",
  "ts": 1775075100,
  "subject_ref": {"node_id": "chg_01H...", "node_kind": "ReviewNode"},
  "rule_code": "TRN_EVID_SIGNED_TO_CHALLENGE_OPEN",
  "metadata": {}
}
```

### Event properties
- append-only
- minimal
- factual
- no hidden authority

---

## 8. Reducer signatures

A future reducer API may look like:

```python
def reduce_command(
    command: dict,
    state: dict,
    context: dict | None = None,
) -> dict:
    ...
```

But a more structured form is preferable:

```python
class ReduceResult(BaseModel):
    updated_objects: list[BaseModel]
    created_objects: list[BaseModel]
    events: list[dict]
    warnings: list[str] = []
```

Suggested reducer family interface:

```python
def reduce_evidence(command: BaseModel, state: dict, context: dict | None = None) -> ReduceResult: ...
def reduce_challenge(command: BaseModel, state: dict, context: dict | None = None) -> ReduceResult: ...
def reduce_research(command: BaseModel, state: dict, context: dict | None = None) -> ReduceResult: ...
def reduce_runtime_collision(command: BaseModel, state: dict, context: dict | None = None) -> ReduceResult: ...
def reduce_graph_projection(command: BaseModel, state: dict, context: dict | None = None) -> ReduceResult: ...
```

---

## 9. Reducer laws

These should be treated as hard design laws.

## 9.1 Law of no hidden mutation
Every meaningful state change must occur through:
- reducer entry
- event emission
- persisted result

No direct attribute patching in route handlers.

---

## 9.2 Law of no display authority
A graph/read reducer may derive display state.
It may never:
- alter runtime truth,
- elevate evidence state,
- or grant executability.

---

## 9.3 Law of derived re-entry
If a research path becomes viable again,
the reducer should create a **new runtime candidate object**.

It must not flip:
- `ResearchNode.status.lane = runtime`
- `ResearchNode.status.executable = true`

That would be an illegal shortcut.

---

## 9.4 Law of preserved lineage
If review modifies interpretation:
- old object remains in lineage
- new interpretation may be attached
- split may derive new branch
- prior history must remain accessible

---

## 9.5 Law of fail-closed ambiguity
If reducer route is ambiguous:
- reject
- emit explicit rule code
- no partial mutation
- no optimistic guess

---

## 10. Core reducer patterns

## 10.1 In-place safe update pattern

Use only when:
- same object family
- same lane
- legal state progression
- lineage not destroyed

Examples:
- `EvidenceRecord.observed -> witnessed`
- `ChallengeRecord.open -> queued`
- `ChallengeRecord.queued -> under_review`
- `ChallengeRecord.under_review -> resolved_uphold`

Pseudo-pattern:

```python
def reducer(state_obj, command, guard):
    if not guard.allowed:
        raise TransitionError(guard.rule_code)

    updated = state_obj.model_copy(deep=True)
    # apply minimal state mutation
    return ReduceResult(
        updated_objects=[updated],
        created_objects=[],
        events=[...],
    )
```

---

## 10.2 Derived object pattern

Use when:
- lane changes
- new object family appears
- lineage must branch
- previous object must remain historically true

Examples:
- `ExecutionNode -> GlitchNode`
- `GlitchNode -> ResearchNode`
- `ResearchNode -> BackwardNode`
- review split -> revised branch object
- research -> runtime candidate

Pseudo-pattern:

```python
def derive_research_from_glitch(glitch, command, guard):
    if not guard.allowed:
        raise TransitionError(guard.rule_code)

    research = ResearchNode(...)
    event = {"event_type": "ResearchNodeDerived", ...}

    return ReduceResult(
        updated_objects=[],
        created_objects=[research],
        events=[event],
    )
```

---

## 11. Recommended reducer map

## 11.1 Evidence reducer routes

| Command | Input object | Output | Mutation type |
|---|---|---|---|
| `RecordObservation` | `EvidenceRecord` | updated `EvidenceRecord` | in-place safe update |
| `AttachWitness` | `EvidenceRecord` or witness-capable node | updated object | in-place safe update |
| `SignEvidence` | `EvidenceRecord` | updated `EvidenceRecord` | in-place safe update |
| `ExpireEvidence` | `EvidenceRecord` | updated `EvidenceRecord` | in-place safe update |

---

## 11.2 Challenge reducer routes

| Command | Input object | Output | Mutation type |
|---|---|---|---|
| `OpenChallenge` | target object + evidence context | new `ChallengeRecord`, maybe updated target evidence state | derived + update |
| `QueueChallenge` | `ChallengeRecord` | updated `ChallengeRecord` | in-place safe update |
| `StartReview` | `ChallengeRecord` | updated `ChallengeRecord` | in-place safe update |
| `ResolveReview` | `ChallengeRecord` | new `ReviewRecord`, updated challenge, maybe derived object | mixed |
| `ExpireChallenge` | `ChallengeRecord` | updated `ChallengeRecord` | in-place safe update |
| `ArchiveChallenge` | `ChallengeRecord` | updated `ChallengeRecord` | in-place safe update |

---

## 11.3 Research reducer routes

| Command | Input object | Output | Mutation type |
|---|---|---|---|
| `DeriveResearchNode` | `GlitchNode` | new `ResearchNode` | derived |
| `DeriveBackwardNode` | `ResearchNode` | new `BackwardNode` | derived |
| `SetReopenability` | `ResearchNode` | updated `ResearchNode` | in-place safe update |
| `CreateRuntimeCandidateFromResearch` | `ResearchNode` + gate | new runtime candidate | derived |
| `ArchiveResearchNode` | `ResearchNode` | updated `ResearchNode` or historical view | in-place safe update or derived historical |

---

## 11.4 Runtime collision reducer routes

| Command | Input object | Output | Mutation type |
|---|---|---|---|
| `RegisterRuntimeCollision` | `ExecutionNode` | new `GlitchNode` | derived |
| `BindCollisionWitness` | `GlitchNode` | updated `GlitchNode` | in-place safe update |
| `ArchiveExecutionNode` | `ExecutionNode` | updated/historical | in-place safe update or derived |

---

## 11.5 Graph/read reducer routes

| Command | Input object | Output | Mutation type |
|---|---|---|---|
| `ProjectGraphNode` | typed source object | new `GraphNodeView` | derived |
| `ProjectGraphEdge` | relation info | new `GraphEdgeView` | derived |
| `BuildGraphSlice` | graph nodes/edges | new `GraphSlice` | derived |

### Important note
Graph reducers are read-only derivatives.
They must never write back into runtime truth.

---

## 12. Guard integration

Reducers should never be called without prior guard result.

Suggested guard object input:

```python
class GuardDecision(BaseModel):
    allowed: bool
    transition_class: Literal["LEGAL", "CONDITIONAL", "FORBIDDEN"]
    rule_code: str
    reason: str
    required_conditions: list[str] = []
```

Reducer rule:
- `FORBIDDEN` -> reject
- `CONDITIONAL` with unsatisfied conditions -> reject
- `LEGAL` -> proceed
- `CONDITIONAL` with satisfied conditions -> proceed

---

## 13. Example reducer sketches

## 13.1 `OpenChallenge` reducer sketch

```python
def reduce_open_challenge(
    target_obj,
    evidence_obj,
    command,
    guard,
):
    if not guard.allowed:
        raise ValueError(guard.rule_code)

    challenge = ChallengeRecord(
        challenge_id=command.challenge_id,
        target_ref=command.target_ref,
        opened_by_role=command.opened_by_role,
        opened_by_subject=command.opened_by_subject,
        challenge_type=command.challenge_type,
        reason=command.reason,
        opened_ts=command.opened_ts,
        deadline_ts=command.deadline_ts,
        status=ChallengeStatus.OPEN,
        new_evidence_refs=[],
        metadata=command.metadata,
    )

    updated_evidence = evidence_obj.model_copy(deep=True)
    updated_evidence.evidence_state = EvidenceState.CHALLENGE_OPEN

    return {
        "updated_objects": [updated_evidence],
        "created_objects": [challenge],
        "events": [
            {
                "event_type": "ChallengeOpened",
                "rule_code": guard.rule_code,
                "ts": command.opened_ts,
            }
        ],
    }
```

---

## 13.2 `DeriveResearchNode` reducer sketch

```python
def reduce_derive_research(glitch_obj, command, guard):
    if not guard.allowed:
        raise ValueError(guard.rule_code)

    research = ResearchNode(
        node_id=command.node_id,
        source_glitch_ref=NodeRef(
            node_id=glitch_obj.node_id,
            node_kind=NodeKind.GLITCH_NODE,
        ),
        created_ts=command.created_ts,
        title=command.title,
        summary=command.summary,
        missing_evidence=command.missing_evidence,
        required_resources=command.required_resources,
        reopenability=ReopenabilityState.EVIDENCE_REQUIRED,
        status=StatusTuple(
            lane=Lane.RESEARCH,
            active=True,
            evidence_state=EvidenceState.ASSERTED,
            challenge_status=None,
            reopenability=ReopenabilityState.EVIDENCE_REQUIRED,
            expired=False,
            executable=False,
            render_mode_min=RenderMode.NORMAL,
        ),
        witness_ref=None,
        challenge_ref=None,
        metadata=command.metadata,
    )

    return {
        "updated_objects": [],
        "created_objects": [research],
        "events": [
            {
                "event_type": "ResearchNodeDerived",
                "rule_code": guard.rule_code,
                "ts": command.created_ts,
            }
        ],
    }
```

---

## 13.3 `CreateRuntimeCandidateFromResearch` reducer sketch

```python
def reduce_create_runtime_candidate(research_obj, gate_obj, command, guard):
    if not guard.allowed:
        raise ValueError(guard.rule_code)

    runtime_candidate = ExecutionNode(
        node_id=command.node_id,
        action_kind=command.action_kind,
        scope=command.scope,
        started_ts=command.created_ts,
        ended_ts=None,
        actor_ref=command.actor,
        status=StatusTuple(
            lane=Lane.RUNTIME,
            active=True,
            evidence_state=EvidenceState.ASSERTED,
            challenge_status=None,
            reopenability=None,
            expired=False,
            executable=False,  # important: candidate first, not immediate execution
            render_mode_min=RenderMode.NORMAL,
        ),
        metadata={
            "derived_from_research_ref": research_obj.node_id,
            **command.metadata,
        },
    )

    return {
        "updated_objects": [],
        "created_objects": [runtime_candidate],
        "events": [
            {
                "event_type": "RuntimeCandidateCreated",
                "rule_code": guard.rule_code,
                "ts": command.created_ts,
            }
        ],
    }
```

### Important detail
Even here, candidate creation does **not** mean automatic execution.
This avoids fake smoothness.

---

## 14. Reducer-side anti-patterns

These must be treated as design violations.

### 14.1 Route-handler mutation
Bad:
- route handler changes object state directly
- no reducer
- no event
- no guard result persistence

### 14.2 UI-origin mutation
Bad:
- graph click changes runtime truth
- display layer sets evidence state
- cinematic surface opens privilege path

### 14.3 In-place lane mutation
Bad:
- `ResearchNode.status.lane = runtime`
- `GlitchNode.status.lane = research`
- `GraphNodeView` repurposed as truth object

### 14.4 Silent downgrade / upgrade
Bad:
- evidence state silently strengthened
- review outcome implied without `ReviewRecord`
- expired object quietly treated as current

### 14.5 Best-effort ambiguity
Bad:
- reducer “tries to do something reasonable”
- no explicit rule code
- partial mutation emitted anyway

---

## 15. Minimal reducer test expectations

Every reducer route should eventually have tests for:

- legal happy path
- forbidden path
- conditional path with missing guard
- conditional path with satisfied guard
- lineage preserved
- event emitted
- no extra mutation
- no graph-side writeback

Examples:
- `OpenChallenge` produces one `ChallengeRecord`
- `DeriveResearchNode` does not mutate `GlitchNode` into research
- `CreateRuntimeCandidateFromResearch` creates new runtime candidate but does not set `ResearchNode.executable`
- `ResolveReview(branch_split)` emits `ReviewRecord` and preserves old lineage

---

## 16. Suggested persistence discipline

Reducers should not write directly to:
- UI cache
- display artifacts
- graph export bundle

Preferred order:
1. persist updated/created truth objects
2. persist events
3. refresh read models
4. refresh graph views
5. export if requested

This order prevents:
cosmetic persistence racing ahead of truth persistence.

---

## 17. Suggested future file landing

A future code landing might look like:

```text
models/
reducers/
  evidence.py
  challenge.py
  research.py
  runtime.py
  graph.py
events/
guards/
validators/
```

### Most likely first landing zones in `ester-clean-code`
- runtime collision / quarantine logic near `drift_quarantine`
- windows near `comm_window`
- research lane via `memory_manager` / `chroma_adapter`
- legality via `validator/*` + `rules/*`
- read models via thinking/memory-flow HTTP plugins

This pack does not force exact file names.
It forces design discipline.

---

## 18. Explicit bridge

This reducer/state-machine pack is the bridge between:
- typed models,
- legal transition rules,
- and actual future mutation logic.

It makes one thing explicit:

**state change is not just about what is allowed in theory. It is about what the system is allowed to physically do to its own objects, in what order, and with what evidence trail.**

---

## 19. Hidden bridges

### Hidden Bridge 1 — Cybernetics
A system is defined not only by what it stores, but by how its state may evolve under control and refusal.

### Hidden Bridge 2 — Information Theory
Reducer discipline preserves lineage by ensuring that every meaningful change becomes an eventful transformation rather than an overwritten narrative.

---

## 20. Earth paragraph

In a real industrial control system, the machine does not go from “fault” to “repaired” because someone changed a field in a dashboard table. A technician opens a ticket, an inspection happens, a signed result is recorded, and only then does the machine become eligible for return to service. If your software model lets the field flip directly, you have not digitized the workflow — you have falsified it. Reducers are where that falsification must be blocked.

---

## 21. Final position

`Reducer / State Machine Draft Pack v0.1` gives the stack its first real muscles.

Not because it executes yet.

But because it defines:
- who asks for change,
- who decides legality,
- what mutates,
- what gets derived,
- what gets recorded,
- and what must never be allowed to mutate in place.

That is where a concept starts becoming a machine.
