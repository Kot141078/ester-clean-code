# Canonical Event Taxonomy Pack v0.1

**Status:** Draft event taxonomy pack  
**Scope:** Canonical event language for the first implementation phase of the new stack  
**Purpose:** Define a stable, machine-readable, audit-compatible vocabulary for events emitted by reducers, guards, runtime collision logic, evidence flows, review flows, and graph/read projections

**Builds on**
- `Object Model Draft Pack v0.1`
- `Schema Pack v0.1`
- `Semantic Validator Rules Pack v0.1`
- `Transition Legality Matrix Pack v0.1`
- `Pydantic Models Draft Pack v0.1`
- `Reducer / State Machine Draft Pack v0.1`
- `Test Matrix Pack v0.1`

---

## 1. Why this pack exists

Objects define what exists.

Schemas define structure.

Semantic rules define meaning.

Transition matrices define legal routes.

Reducers define how change happens.

Tests define what must be proven.

But a long-lived system still needs one more thing:

**a canonical language for what actually happened.**

Without an event taxonomy, implementation drifts toward:
- ad hoc event names,
- duplicated meanings,
- soft human-readable blobs,
- event inflation,
- hidden side effects with no stable record,
- and audit trails that sound persuasive but are mechanically weak.

This pack exists to stop that drift.

It defines:
- event families,
- canonical event names,
- required event envelope fields,
- lineage references,
- severity and class tags,
- event admissibility rules,
- and red lines against fake or laundering events.

---

## 2. Event principles

### 2.1 Events describe facts, not wishes
A command is a request.
An event is a recorded outcome.

### 2.2 Events are append-only
An event may be superseded in interpretation.
It must not be retroactively rewritten into non-existence.

### 2.3 Event names must be narrow
Avoid giant, vague names like:
- `SystemUpdated`
- `ThingChanged`
- `ReviewProcessed`

Prefer:
- `ChallengeOpened`
- `ReviewResolvedSplit`
- `RuntimeCollisionRegistered`
- `ResearchNodeDerived`

### 2.4 Event taxonomy must preserve category separation
There must not be one blended stream where:
- runtime collision,
- evidence strengthening,
- graph refresh,
- and UI navigation
all look equivalent.

### 2.5 Graph/read events never imply authority
A projection event can prove that a view was built.
It cannot prove runtime legitimacy.

---

## 3. Event families

Canonical event families:

1. **runtime events**
2. **collision events**
3. **evidence events**
4. **challenge events**
5. **review events**
6. **research events**
7. **reopenability events**
8. **historical/archive events**
9. **graph/read events**
10. **validator/guard events**
11. **integrity events**
12. **operator/audit events**

These families are not aesthetic categories.
They define what kind of system fact is being recorded.

---

## 4. Canonical event envelope

Every canonical event should fit inside a stable envelope.

## 4.1 Required event fields

```json
{
  "event_id": "evt_01H...",
  "event_type": "ChallengeOpened",
  "event_family": "challenge",
  "ts": 1775075100,
  "subject_ref": {
    "node_id": "chg_01H...",
    "node_kind": "ReviewNode"
  },
  "rule_code": "TRN_EVID_SIGNED_TO_CHALLENGE_OPEN",
  "event_class": "state_change",
  "severity": "INFO",
  "lineage_ref": "lin_01H...",
  "metadata": {}
}
```

Required fields:
- `event_id`
- `event_type`
- `event_family`
- `ts`
- `subject_ref`
- `event_class`
- `metadata`

Strongly recommended:
- `rule_code`
- `lineage_ref`

Optional:
- `caused_by_command`
- `actor_ref`
- `related_refs`
- `witness_ref`
- `integrity_root`
- `notes`

---

## 4.2 Envelope field meanings

### `event_id`
Stable unique event identifier.

### `event_type`
Canonical narrow event name.

### `event_family`
One of the defined family names.

### `ts`
Unix timestamp of recorded occurrence.

### `subject_ref`
What primary object this event is about.

### `rule_code`
Which legality or semantic rule governed the transition, if relevant.

### `event_class`
Event semantic class, see below.

### `severity`
Operational significance, not moral drama.

### `lineage_ref`
Branch / object lineage anchor so reinterpretation can preserve historical continuity.

### `metadata`
Small, typed, purpose-specific extra payload.

---

## 5. Event classes

Event classes should be explicitly tagged.

```text
state_change      -> object changed legal state
derived_object    -> new object created from prior object(s)
validation        -> validator outcome
guard_decision    -> allow/deny/conditional guard result
projection        -> read/graph projection built or refreshed
integrity         -> hash/witness/signature/chain outcome
audit             -> audit trail or operator inspection outcome
lifecycle         -> archival / expiry / historical retention event
```

These classes help prevent event streams from becoming semantically flat.

---

## 6. Severity levels

Suggested event severities:

- `DEBUG`
- `INFO`
- `NOTICE`
- `WARNING`
- `ERROR`
- `CRITICAL`

### Guidance
- `RuntimeCollisionRegistered` -> usually `WARNING` or `ERROR`
- `ChallengeOpened` -> `INFO`
- `ReviewResolvedSplit` -> `NOTICE` or `INFO`
- `IntegrityVerificationFailed` -> `ERROR`
- `ProjectionBuilt` -> `DEBUG` or `INFO`

Do not inflate every event to drama.
Noise destroys operator trust.

---

## 7. Runtime event family

These events describe ordinary runtime object lifecycle.

### Canonical runtime events
- `ExecutionStarted`
- `ExecutionEnded`
- `ExecutionArchived`
- `RuntimeCandidateCreated`
- `RuntimeCandidatePromoted`
- `RuntimeCandidateRejected`

### Example meanings

#### `ExecutionStarted`
An `ExecutionNode` began active runtime life.

#### `ExecutionEnded`
Execution completed or terminated without necessarily meaning failure.

#### `RuntimeCandidateCreated`
A new runtime candidate object was derived, usually from research under guard discipline.

#### `RuntimeCandidatePromoted`
A candidate cleared all guards and became eligible for actual execution.

### Red line
`RuntimeCandidateCreated` must not be treated as `ExecutionStarted`.

Those are different events.

---

## 8. Collision event family

These events describe runtime meeting a boundary.

### Canonical collision events
- `RuntimeCollisionRegistered`
- `GlitchNodeCreated`
- `CollisionWitnessAttached`
- `CollisionEscalated`
- `CollisionArchived`

### Meanings

#### `RuntimeCollisionRegistered`
A runtime path encountered a typed boundary or failure.

#### `GlitchNodeCreated`
A `GlitchNode` was derived from that collision.

#### `CollisionWitnessAttached`
Witness material now binds to the collision record.

### Red line
A collision event must not be renamed into a “recovery” event simply because a later branch succeeded.
The collision occurred.
It stays.

---

## 9. Evidence event family

These events describe evidence strengthening or degradation.

### Canonical evidence events
- `ObservationRecorded`
- `WitnessAttached`
- `EvidenceSigned`
- `EvidenceChallengeOpened`
- `EvidenceSettled`
- `EvidenceExpired`
- `EvidenceRevalidated`
- `EvidenceDowngraded`
- `EvidenceUpgraded`

### Meanings

#### `ObservationRecorded`
Evidence moved from asserted to observed context.

#### `WitnessAttached`
Witness binding was added.

#### `EvidenceSigned`
Integrity/signature step completed.

#### `EvidenceExpired`
Evidence standing degraded by time/context drift.

#### `EvidenceRevalidated`
Previously expired evidence regained standing through explicit process.

### Red line
There is no canonical event called:
- `EvidenceBecameTrue`
- `EvidenceBecameLegitimate`

Evidence events do not settle ontology or legitimacy by themselves.

---

## 10. Challenge event family

These events track challenge lifecycle.

### Canonical challenge events
- `ChallengeOpened`
- `ChallengeQueued`
- `ChallengeReviewStarted`
- `ChallengeDismissed`
- `ChallengeExpired`
- `ChallengeArchived`

### Meanings

#### `ChallengeOpened`
A dispute object was created.

#### `ChallengeQueued`
The challenge entered formal processing.

#### `ChallengeReviewStarted`
The review phase actually began.

### Red line
`ChallengeOpened` is not the same as:
- `DisputeAccepted`
- `DisputeWon`
- `TargetProvenWrong`

Opening a challenge means exactly one thing:
a challenge exists.

---

## 11. Review event family

These events record the review outcome layer.

### Canonical review events
- `ReviewResolvedUphold`
- `ReviewResolvedModify`
- `ReviewResolvedSplit`
- `ReviewResolvedScopeRestriction`
- `ReviewSigned`
- `ReviewArchived`

### Meanings

#### `ReviewResolvedUphold`
Original interpretation stands.

#### `ReviewResolvedModify`
Interpretation changed.

#### `ReviewResolvedSplit`
Historical branch preserved and revised branch created.

#### `ReviewResolvedScopeRestriction`
The object remains but with reduced allowed scope.

### Red line
No event should pretend that a split is just a modify.
`Split` is special because it preserves two visible branches.

---

## 12. Research event family

These events describe quarantined future work objects.

### Canonical research events
- `ResearchNodeDerived`
- `BackwardNodeDerived`
- `ResearchNodeArchived`
- `ResearchNodeRecast`
- `ResearchLaneStored`
- `ResearchLaneRetrieved`

### Meanings

#### `ResearchNodeDerived`
A `ResearchNode` was created from a `GlitchNode`.

#### `BackwardNodeDerived`
A `BackwardNode` was created from a `ResearchNode`.

#### `ResearchNodeRecast`
A historical or prior research object was reinterpreted into a new research object without mutating the old one.

### Red line
There is no event:
- `ResearchBecameExecution`

That route must always be represented through:
- gate
- candidate creation
- promotion
not a single magical jump.

---

## 13. Reopenability event family

These events track movement across reopenability states.

### Canonical reopenability events
- `ReopenabilitySetToEvidenceRequired`
- `ReopenabilitySetToReviewRequired`
- `ReopenabilitySetToReopenable`
- `ReopenabilitySetToClosed`
- `RuntimeCandidateDerivedFromResearch`

### Meanings

#### `ReopenabilitySetToReopenable`
The research object is now legally eligible for controlled re-entry path.

#### `RuntimeCandidateDerivedFromResearch`
A new runtime candidate was created as a derivative object.

### Red line
`ReopenabilitySetToReopenable` does not equal execution start.
It only opens the next narrow gate.

---

## 14. Historical / archive event family

These events preserve time and decay.

### Canonical historical events
- `ObjectArchived`
- `ObjectExpired`
- `HistoricalLineageBound`
- `HistoricalProjectionBuilt`

### Meanings

#### `ObjectArchived`
Object moved into archival standing.

#### `ObjectExpired`
Object lost current standing but remains historically visible.

### Red line
Archive is not deletion.
There should be no canonical event named:
- `ObjectRemovedFromHistory`

unless an explicit retention/policy regime truly requires deletion and says so separately.

---

## 15. Graph / read event family

These events describe derived visibility only.

### Canonical graph/read events
- `GraphNodeProjected`
- `GraphEdgeProjected`
- `GraphSliceBuilt`
- `GraphSliceRefreshed`
- `EvidenceBadgeProjected`
- `AuditViewBuilt`
- `PedagogicalViewBuilt`

### Meanings

#### `GraphSliceBuilt`
A graph slice was assembled from source truth.

#### `EvidenceBadgeProjected`
Badge/display metadata was refreshed from source evidence state.

### Red line
Graph/read events must never be the only evidence that something happened.
They are projections.

---

## 16. Validator / guard event family

These events make rule enforcement visible.

### Canonical validator/guard events
- `SchemaValidationFailed`
- `SemanticValidationFailed`
- `TransitionForbidden`
- `ConditionalTransitionRejected`
- `GuardAllowed`
- `GuardDenied`
- `IntegrityCheckPassed`
- `IntegrityCheckFailed`

### Meanings

#### `TransitionForbidden`
A transition was explicitly blocked by legality matrix.

#### `ConditionalTransitionRejected`
A route was legal in principle, but required conditions were missing.

#### `GuardDenied`
A guard said no.

### Red line
Do not collapse:
- `SemanticValidationFailed`
- `TransitionForbidden`
- `GuardDenied`

These are different layers and must stay visible as different layers.

---

## 17. Integrity event family

These events capture integrity substrate outcomes.

### Canonical integrity events
- `PayloadHashed`
- `MerkleRootComputed`
- `WitnessEnvelopeBound`
- `WitnessChainVerified`
- `WitnessChainBroken`
- `SignatureVerified`
- `SignatureRejected`
- `IntegrityBundleExported`

### Meanings

#### `WitnessEnvelopeBound`
A witness envelope now binds to an object or event set.

#### `WitnessChainVerified`
Chain continuity passed.

#### `WitnessChainBroken`
Chain continuity failed.

### Red line
`SignatureVerified` does not imply:
- policy allowed
- review complete
- action legitimate

It only means signature verification succeeded.

---

## 18. Operator / audit event family

These events describe explicit human/operator interaction with the record.

### Canonical operator/audit events
- `AuditInspectionStarted`
- `AuditInspectionCompleted`
- `OperatorViewedHistoricalObject`
- `OperatorViewedResearchObject`
- `OperatorRequestedExport`
- `AuditBundleExported`
- `AuditBundleVerified`

### Meanings

These events are useful for:
- traceability
- operator accountability
- export discipline

### Red line
Viewing something is not approving it.

There should be no shortcut:
- `OperatorViewedResearchObject` -> implicit reopenability

---

## 19. Lineage requirements

Every event that changes meaning, standing, or derivation should carry lineage information.

### Required lineage on these event types
- `GlitchNodeCreated`
- `ResearchNodeDerived`
- `BackwardNodeDerived`
- `ReviewResolvedModify`
- `ReviewResolvedSplit`
- `RuntimeCandidateDerivedFromResearch`
- `ObjectArchived`
- `EvidenceRevalidated`

### Minimum lineage fields
- `lineage_ref`
- `parent_refs`
- `subject_ref`

Suggested shape:

```json
{
  "lineage_ref": "lin_01H...",
  "parent_refs": [
    {"node_id": "glitch_01H...", "node_kind": "GlitchNode"}
  ]
}
```

### Red line
No event that derives a new object should exist without parent lineage.

---

## 20. Command-to-event mapping guidance

Commands and events must not share names lazily.

### Good mapping
- command: `OpenChallenge`
- event: `ChallengeOpened`

- command: `ResolveReview`
- events:
  - `ReviewResolvedModify`
  - `ReviewSigned`
  - maybe `HistoricalLineageBound`

### Bad mapping
- command: `ResolveReview`
- event: `ResolveReview`

That hides whether anything actually happened.

---

## 21. Event admissibility rules

### Rule E-001
Every canonical event must belong to exactly one primary event family.

### Rule E-002
Every canonical event must have exactly one canonical `event_type`.

No synonyms at persistence layer.

### Rule E-003
An event name must describe:
- factual outcome
not:
- aspiration
- marketing interpretation
- philosophical label

### Rule E-004
If an event implies derived-object creation, the created object must exist in the same transaction or persisted reducer result.

### Rule E-005
If an event claims review resolution, a `ReviewRecord` must exist.

### Rule E-006
If an event claims evidence signing, signer/witness context must exist.

### Rule E-007
Projection events must never be the sole basis for later runtime mutation.

---

## 22. Forbidden event anti-patterns

These should be treated as design smells or outright violations.

### 22.1 Vague omnibus events
Forbidden style:
- `SystemUpdated`
- `ObjectProcessed`
- `TransitionApplied`

### 22.2 Success laundering
Forbidden style:
- `CollisionRecovered`
when in reality:
- collision happened
- later research derived a future path

These are different facts.

### 22.3 Display laundering
Forbidden style:
- `GraphApproved`
- `ViewValidated`
if the event only concerns projection refresh

### 22.4 Authority laundering
Forbidden style:
- `EvidenceAuthorizedAction`
if the system did not pass separate policy/guard review

### 22.5 Erasure events without policy
Forbidden style:
- `HistoryRemoved`
- `BranchCleaned`
unless there is an explicit retention policy object and audit justification

---

## 23. Suggested machine-readable taxonomy registry

A future static registry may look like:

```python
EVENT_REGISTRY = {
    "ChallengeOpened": {
        "family": "challenge",
        "class": "state_change",
        "requires_lineage": False,
        "requires_rule_code": True,
    },
    "ResearchNodeDerived": {
        "family": "research",
        "class": "derived_object",
        "requires_lineage": True,
        "requires_rule_code": True,
    },
    "GraphSliceBuilt": {
        "family": "graph_read",
        "class": "projection",
        "requires_lineage": False,
        "requires_rule_code": False,
    },
}
```

This registry should become the single canonical naming source.

---

## 24. Suggested Pydantic draft for events

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Any

class CanonicalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    event_family: str = Field(min_length=1)
    ts: int = Field(ge=0)
    subject_ref: dict[str, Any]
    event_class: str = Field(min_length=1)
    rule_code: str | None = None
    severity: str = Field(min_length=1)
    lineage_ref: str | None = None
    parent_refs: list[dict[str, Any]] = Field(default_factory=list)
    caused_by_command: str | None = None
    actor_ref: str | None = None
    witness_ref: dict[str, Any] | None = None
    integrity_root: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

This is only a draft spine.
The important part is taxonomy discipline, not syntax worship.

---

## 25. Required test links

The following event tests should later exist:

- event family uniqueness
- event type uniqueness
- derived-object events require lineage
- review events require `ReviewRecord`
- sign events require signer/witness data
- projection events cannot drive runtime reducers
- no forbidden synonym names
- registry and reducers stay aligned

This pack should eventually connect directly to `Test Matrix Pack v0.1`.

---

## 26. Explicit bridge

This taxonomy pack is the bridge between:
- reducers,
- persistence,
- audit trail,
- and operator truth.

It gives the stack a stable language for what happened,
so later code does not have to improvise history.

---

## 27. Hidden bridges

### Hidden Bridge 1 — Cybernetics
Events are how the system remembers change as change, rather than only as overwritten state.

### Hidden Bridge 2 — Information Theory
A canonical taxonomy reduces entropy in the audit trail by preventing synonym sprawl and event inflation.

---

## 28. Earth paragraph

In a real facility logbook, “breaker tripped,” “maintenance ticket opened,” “inspection signed,” and “panel lamp refreshed” are not interchangeable notes. If the same log language is used for all of them, nobody can tell whether a machine failed, was repaired, was merely inspected, or simply had its display updated. This pack is the software equivalent of insisting that the logbook use the right verbs.

---

## 29. Final position

`Canonical Event Taxonomy Pack v0.1` gives the stack something it badly needs:

a disciplined past tense.

After this point, future implementation should no longer be allowed to say:
- “something changed”
- “the system updated”
- “the review happened somehow”

It should have to say exactly what happened, in the right family, with the right lineage, and without cheating.
