# Test Matrix Pack v0.1

**Status:** Draft validation and test strategy pack  
**Scope:** Mandatory test matrix for the first implementation phase of the new stack  
**Purpose:** Define the minimum test surface required so the stack cannot silently degrade from accountable continuity into aesthetically plausible but unsafe behavior

**Covers**
- object models
- schema layer
- semantic validators
- transition legality
- reducers / state machine
- graph/read projections
- witness/evidence discipline
- quarantine/research boundaries
- anti-collapse rules

---

## 1. Why this pack exists

The previous packs define:
- objects,
- schemas,
- semantic rules,
- legal transitions,
- pydantic models,
- reducers.

That is necessary.

It is still not enough.

Without a test matrix, the system can drift in familiar ways:
- a model remains “valid” but stops meaning what it used to mean,
- a reducer starts mutating in place where it should derive,
- a graph projection begins laundering authority,
- a research path leaks into runtime,
- a signed record is treated as legitimacy,
- review starts rewriting history instead of preserving lineage.

This pack exists to make those failures expensive.

---

## 2. Testing principles

### 2.1 Safety tests are first-class
Tests for:
- refusal,
- quarantine,
- expiry,
- evidence requirements,
- lineage preservation,
- anti-collapse rules

are not “negative tests.”
They are part of the primary contract.

### 2.2 Every layer needs both positive and negative tests
For each layer:
- at least one legal path test
- at least one forbidden path test
- at least one ambiguous or degraded test where relevant

### 2.3 Derived-object behavior must be tested explicitly
The system must prove when it:
- derives a new object,
instead of:
- mutating the old object in place.

### 2.4 Graph is downstream and must be tested as downstream
Graph/read tests must prove:
- no authority flows back upward,
- no graph object mutates runtime truth,
- no cinematic edge gets retyped as execution.

### 2.5 CI must fail on category collapse
If a test demonstrates:
- research -> executable shortcut
- cinematic -> runtime shortcut
- signature -> legitimacy shortcut
- review -> erasure shortcut

that must fail CI.

---

## 3. Test domains

The matrix is organized into the following domains:

### Domain A — model construction tests
Can typed models be instantiated correctly, and do they reject invalid combinations?

### Domain B — schema contract tests
Do machine-readable schemas enforce required fields and shape correctly?

### Domain C — semantic validator tests
Do semantically incoherent objects fail even when structurally valid?

### Domain D — transition legality tests
Do legal/conditional/forbidden routes behave correctly?

### Domain E — reducer tests
Do reducers:
- mutate only when legal,
- derive when necessary,
- emit events,
- preserve lineage,
- fail closed when ambiguous?

### Domain F — graph/read tests
Do graph projections remain read-only and non-authoritative?

### Domain G — witness/evidence tests
Do witness/signature/evidence rules hold under normal and adversarial cases?

### Domain H — anti-collapse regression tests
Does the stack resist the exact shortcuts it was designed to forbid?

---

## 4. Test result classes

Each test should be tagged as one or more of:

- `contract`
- `safety`
- `negative`
- `regression`
- `lineage`
- `audit`
- `integration`
- `performance_smoke`

These tags are important for selective CI runs later.

---

## 5. Minimum test matrix by layer

## 5.1 Object model tests

### Required tests

#### OM-001 — `StatusTuple` legal runtime object
- construct runtime status
- expect success

#### OM-002 — cinematic executable forbidden
- `lane=cinematic`, `executable=true`
- expect model validation failure

#### OM-003 — reopenability lane restriction
- `reopenability != null`, `lane=runtime`
- expect failure

#### OM-004 — expired executable forbidden
- `expired=true`, `executable=true`
- expect failure

#### OM-005 — `GlitchNode` requires execution source kind
- `source_execution_ref.node_kind != ExecutionNode`
- expect failure

#### OM-006 — `ResearchNode` cannot be executable
- `status.executable=true`
- expect failure

#### OM-007 — `BackwardNode` requires research source
- wrong source kind
- expect failure

#### OM-008 — `EvidenceRecord` signed requires signer
- `evidence_state=signed`, `signer=null`
- expect failure

#### OM-009 — `ReviewRecord` reclassify requires class fields
- missing previous/new class
- expect failure

#### OM-010 — `GraphNodeView` may not carry executable field in metadata
- metadata includes executable
- expect failure

---

## 5.2 Schema contract tests

### Required tests

#### SC-001 — required field absence rejects object
- remove required field from each canonical schema family
- expect schema rejection

#### SC-002 — enum membership enforcement
- inject invalid enum value
- expect rejection

#### SC-003 — union ref shape correctness
- `target_ref` malformed for evidence/challenge
- expect rejection

#### SC-004 — time window deadline ordering handled downstream
- confirm structural shape accepted only when numeric fields exist
- semantic or model validation handles actual ordering

#### SC-005 — additionalProperties forbidden
- inject unknown field
- expect rejection

---

## 5.3 Semantic validator tests

### Required tests

#### SV-001 — `ResearchNode` executable forbidden
- structurally valid object
- semantically invalid
- expect `SEM_RESEARCH_EXECUTABLE_FORBIDDEN`

#### SV-002 — `GlitchNode` challenge status requires challenge window
- structurally valid object
- semantically invalid
- expect `SEM_GLITCH_CHALLENGE_WINDOW_REQUIRED`

#### SV-003 — `EvidenceRecord` cinematic-only runtime target forbidden
- expect `SEM_EVIDENCE_CINEMATIC_TARGET_FORBIDDEN`

#### SV-004 — graph lane/badge mismatch
- runtime lane + cinematic badge
- expect `SEM_GRAPH_LANE_BADGE_MISMATCH`

#### SV-005 — challenge evidence mismatch
- `challenge_status != null`, evidence too weak
- expect `SEM_CHALLENGE_EVIDENCE_MISMATCH`

#### SV-006 — review split requires lineage
- outcome split without split metadata
- expect `SEM_REVIEW_SPLIT_LINEAGE_REQUIRED`

#### SV-007 — signer does not imply legitimacy
- object metadata claims legitimacy only because signed
- expect semantic rejection

---

## 5.4 Transition legality tests

### Required tests

#### TL-001 — asserted -> observed legal
- expect allowed

#### TL-002 — observed -> witnessed conditional
- missing witness -> reject
- with witness -> allow

#### TL-003 — witnessed -> signed conditional
- missing signer -> reject
- signer + witness -> allow

#### TL-004 — cinematic_only -> witnessed forbidden
- expect forbidden

#### TL-005 — open -> queued legal
- expect allowed

#### TL-006 — open -> resolved_uphold forbidden
- expect forbidden

#### TL-007 — research lane -> runtime lane forbidden in place
- expect forbidden

#### TL-008 — research executable false -> true forbidden in place
- expect forbidden

#### TL-009 — expired challenge -> open forbidden
- expect forbidden

#### TL-010 — expired evidence -> witnessed only through revalidation path
- no revalidation -> reject
- explicit revalidation -> conditional allow

---

## 5.5 Reducer tests

### Required tests

#### RD-001 — `OpenChallenge` creates challenge and updates evidence state
- expect:
  - one new `ChallengeRecord`
  - one updated evidence object
  - one event
  - no unrelated mutation

#### RD-002 — `DeriveResearchNode` derives instead of mutating glitch
- expect:
  - new `ResearchNode`
  - original `GlitchNode` preserved
  - event emitted

#### RD-003 — `DeriveBackwardNode` derives from research
- expect new `BackwardNode`
- original `ResearchNode` unchanged except lineage additions if any

#### RD-004 — `CreateRuntimeCandidateFromResearch` creates new runtime candidate
- expect:
  - new runtime object
  - `ResearchNode` remains non-executable
  - event emitted

#### RD-005 — reducer fail-closed on forbidden guard
- guard says forbidden
- expect no mutation, no created object, explicit exception/result

#### RD-006 — reducer fail-closed on missing conditional guard
- conditional route without evidence/review
- expect reject

#### RD-007 — review split preserves lineage
- expect:
  - `ReviewRecord`
  - original lineage preserved
  - new branch object exists
  - no erasure

#### RD-008 — graph reducer cannot write back into runtime truth
- attempt graph projection plus runtime side effect
- expect failure

---

## 5.6 Graph/read tests

### Required tests

#### GR-001 — graph projection from runtime truth
- create `GraphNodeView` from source object
- expect derived view only

#### GR-002 — graph node cannot alter source object
- mutate projected view
- expect source object unchanged

#### GR-003 — cinematic edge cannot masquerade as execution edge
- metadata attempts retype
- expect failure

#### GR-004 — audit slice missing integrity root yields notice, not authority
- expect degraded but non-authoritative output

#### GR-005 — graph slice export never upgrades evidence state
- projection refresh may change badge presentation only
- source evidence stays unchanged

---

## 5.7 Witness/evidence tests

### Required tests

#### WE-001 — witness required for witnessed/signed challenge-open states
- test all elevated states without witness
- expect failure where applicable

#### WE-002 — signer required for signed evidence
- expect failure without signer

#### WE-003 — witness attach legal path
- asserted/observed evidence + witness
- expect appropriate update if allowed

#### WE-004 — signature does not imply authority
- even when signed, runtime authority still denied unless policy path exists

#### WE-005 — expired evidence stays visible as historical
- expect:
  - not executable
  - not current
  - still queryable in historical/audit mode

---

## 5.8 Anti-collapse regression tests

These are the most important long-term regression tests.

### Required tests

#### AC-001 — research -> runtime shortcut blocked
- expect failure

#### AC-002 — research -> executable shortcut blocked
- expect failure

#### AC-003 — cinematic -> runtime shortcut blocked
- expect failure

#### AC-004 — cinematic -> witness shortcut blocked
- expect failure

#### AC-005 — signed -> legitimate shortcut blocked
- expect failure

#### AC-006 — review modifies without lineage blocked
- expect failure

#### AC-007 — runtime -> research without glitch intermediary blocked
- expect failure

#### AC-008 — graph projection writeback blocked
- expect failure

---

## 6. Integration test scenarios

## 6.1 Full runtime collision path

**Scenario**
1. Create runtime execution object
2. Register runtime collision
3. Produce `GlitchNode`
4. Attach witness
5. Open challenge
6. Start review
7. Resolve review with modify
8. Derive `ResearchNode`
9. Derive `BackwardNode`

**Assertions**
- each step emits correct event
- no illegal in-place lane mutation
- original lineage preserved
- graph projection later reflects but does not control truth

---

## 6.2 Evidence strengthening path

**Scenario**
1. `EvidenceRecord` asserted
2. record observation
3. attach witness
4. sign evidence
5. open challenge
6. settle through review

**Assertions**
- legal / conditional transitions respected
- missing guards fail closed
- final evidence state consistent with review lineage

---

## 6.3 Reopenability path

**Scenario**
1. `ResearchNode` starts `evidence_required`
2. evidence attached
3. state moves to `review_required`
4. review succeeds
5. state becomes `reopenable`
6. runtime candidate derived

**Assertions**
- no direct research executable flip
- runtime candidate is new object
- original `ResearchNode` remains research-lane

---

## 7. Test matrix by CI level

## 7.1 Fast CI (mandatory on every push)
Must include:
- object model tests
- schema contract tests
- key semantic validator tests
- key anti-collapse regression tests
- key reducer fail-closed tests

Suggested tags:
- `contract`
- `safety`
- `negative`
- `regression`

---

## 7.2 Extended CI (pull request / pre-release)
Must include:
- full transition legality tests
- reducer family tests
- graph/read tests
- witness/evidence tests
- integration scenarios

Suggested tags:
- `integration`
- `lineage`
- `audit`

---

## 7.3 Release gate
Must include:
- all anti-collapse regression tests
- full reducer lineage tests
- witness/evidence integrity path
- graph non-authority tests
- historical preservation tests

---

## 8. Suggested pytest structure

```text
tests/
  test_models_status.py
  test_models_runtime.py
  test_models_research.py
  test_models_evidence.py
  test_models_review.py
  test_graph_views.py
  test_schema_contracts.py
  test_semantic_validators.py
  test_transition_legality.py
  test_reducers_evidence.py
  test_reducers_challenge.py
  test_reducers_research.py
  test_reducers_runtime.py
  test_reducers_graph.py
  test_integration_runtime_collision.py
  test_integration_reopenability.py
  test_regression_anti_collapse.py
```

---

## 9. Required fixture philosophy

Fixtures should prefer:
- small canonical objects
- explicit timestamps
- explicit IDs
- explicit witness refs
- explicit guard decisions

Avoid giant magic fixtures.
They hide the state machine.

Good fixtures:
- `runtime_status()`
- `research_status()`
- `witness_ref()`
- `challenge_window()`
- `guard_allowed()`
- `guard_forbidden(rule_code=...)`
- `minimal_glitch_node()`
- `minimal_research_node()`

---

## 10. Required assertions style

Prefer assertions that prove:
- exact object family created
- exact object family unchanged
- exact event count
- exact rule code
- exact lineage reference presence
- exact field that remained false

Examples:
- `assert research.status.executable is False`
- `assert created[0].__class__.__name__ == "ResearchNode"`
- `assert events[0]["event_type"] == "ResearchNodeDerived"`
- `assert "split_lineage_ref" in review.metadata`

Avoid vague assertions like:
- “result looks good”
- “some object was returned”
- “status changed somehow”

---

## 11. Non-negotiable regression invariants

The following invariants must each have at least one dedicated regression test:

1. research objects never become executable in place  
2. cinematic objects never become authoritative  
3. signature never implies legitimacy by itself  
4. review never erases historical lineage  
5. graph never writes back into runtime truth  
6. challenge never settles without review  
7. expired objects never silently become current  
8. runtime-to-research path never bypasses glitch derivation  

These are the identity tests of the stack.

---

## 12. Performance smoke tests

Not full perf engineering yet, just smoke.

### Required smokes

#### PF-001
construct 1,000 `GraphNodeView` objects
- expect stable memory / acceptable runtime

#### PF-002
run 1,000 semantic validations on canonical objects
- expect no catastrophic slowdown

#### PF-003
run reducer derivation chain for collision -> research -> backward
- expect no hidden O(n²) growth in small test window

These are not optimization trophies.
They are sanity guards against accidental complexity explosions.

---

## 13. Test naming convention

Recommended format:

```text
test_<layer>__<scenario>__<expected_behavior>
```

Examples:
- `test_semantic__research_node_executable__rejects`
- `test_reducer__derive_research_from_glitch__creates_new_object`
- `test_graph__cinematic_edge_retyped_as_execution__rejects`
- `test_transition__challenge_open_to_resolved_uphold__forbidden`

This naming style makes CI failure meaning obvious.

---

## 14. Explicit bridge

This test matrix is the bridge from:
- normative design
- to disciplined implementation

because it defines what future code must prove,
not merely what future documents say.

---

## 15. Hidden bridges

### Hidden Bridge 1 — Cybernetics
A regulator that cannot be tested at its refusal boundaries is not actually a regulator.

### Hidden Bridge 2 — Information Theory
Regression tests preserve category separation by preventing later code from compressing distinct objects into convenient but lossy shortcuts.

---

## 16. Earth paragraph

When a machine is certified, nobody says “the design document was elegant, so let us assume the interlock still works.” They test the interlock. They test that the emergency stop still cuts power. They test that the maintenance bypass does not energize the wrong circuit. They test that the warning lamp does not quietly become the control path. This pack is that mentality, translated into software.

---

## 17. Final position

`Test Matrix Pack v0.1` defines the minimum proof burden for the stack.

After this point, future implementation should not be allowed to hide behind:
- good intentions,
- elegant abstractions,
- or passing demos.

It should have to pass the machine room.
