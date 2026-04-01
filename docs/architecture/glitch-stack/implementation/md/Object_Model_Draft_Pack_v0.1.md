# Object Model Draft Pack v0.1

**Status:** Canonical object draft pack  
**Scope:** First typed object layer for the new stack over the public `ester-clean-code` skeleton  
**Purpose:** Define the canonical conceptual objects, enums, relations, and invariants needed to move from bridge documents to future implementation

**Target stack**
- `L4 Glitch Map`
- `ResearchNode / BackwardNode`
- `Cinematic Walkthrough Layer`
- `Witness Overlay / Evidence Notation`
- `Challenge / Review Protocol`
- `State Transition Matrix / Status Algebra`

---

## 1. Why this pack exists

Until now, the work produced:

- conceptual layers,
- minimal stack logic,
- graph grammar,
- rendering rules,
- evidence notation,
- challenge/review protocol,
- status algebra,
- bridge-to-code documents,
- and file-excavation notes.

That was necessary.

But a system does not become implementable until its concepts are forced into **objects**.

This pack is the first attempt to define those objects.

It is not final code.
It is the typed skeleton that future code, schemas, validators, and graph views can grow around.

---

## 2. Modeling principles

### 2.1 Runtime truth stays below representation
Execution truth lives in runtime organs.
Graph and UI objects are projections, not sovereign authorities.

### 2.2 Evidence is not authority
An object may be:
- visible,
- witnessed,
- signed,
- challenge-open,
without being executable.

### 2.3 Research remains quarantined
Speculative or incomplete future paths must exist as explicit objects,
but they must not leak silently into runtime execution.

### 2.4 Revision must preserve lineage
Review modifies interpretation.
It must not erase the historical record that something was challenged or changed.

### 2.5 Typed objects beat narrative smoothing
If a concept matters for safety, it deserves:
- a type,
- explicit fields,
- validation,
- and forbidden transition rules.

---

## 3. Canonical package view

Future implementation does not need to use these exact module names,
but the conceptual package map should converge toward something like:

- `models/core.py`
- `models/status.py`
- `models/glitch.py`
- `models/research.py`
- `models/evidence.py`
- `models/review.py`
- `models/graph.py`
- `models/guards.py`

This pack defines what would live there.

---

## 4. Foundational enums

## 4.1 `Lane`

```python
class Lane(str, Enum):
    RUNTIME = "runtime"
    RESEARCH = "research"
    WITNESS = "witness"
    HISTORICAL = "historical"
    CINEMATIC = "cinematic"
```

### Meaning
- `runtime` -> execution-bearing or execution-derived truth
- `research` -> quarantined non-executive possibility
- `witness` -> evidence-facing lineage objects
- `historical` -> expired or archived but preserved objects
- `cinematic` -> representational-only projection

---

## 4.2 `NodeKind`

```python
class NodeKind(str, Enum):
    EXECUTION_NODE = "ExecutionNode"
    GLITCH_NODE = "GlitchNode"
    RESEARCH_NODE = "ResearchNode"
    BACKWARD_NODE = "BackwardNode"
    WITNESS_NODE = "WitnessNode"
    REVIEW_NODE = "ReviewNode"
    GRAPH_VIEW_NODE = "GraphViewNode"
```

---

## 4.3 `EdgeKind`

```python
class EdgeKind(str, Enum):
    EXECUTION_FLOW = "execution_flow"
    COLLISION = "collision"
    DERIVES_RESEARCH = "derives_research"
    NEEDS_EVIDENCE = "needs_evidence"
    WITNESS_BINDS = "witness_binds"
    CHALLENGE_OPENS = "challenge_opens"
    REVIEW_RESOLVES = "review_resolves"
    REVIEW_SPLIT = "review_split"
    CINEMATIC_PROJECTS = "cinematic_projects"
```

---

## 4.4 `RuntimeLockType`

```python
class RuntimeLockType(str, Enum):
    ENERGY_LOCK = "EnergyLock"
    TIME_LOCK = "TimeLock"
    THERMAL_LOCK = "ThermalLock"
    PRIVILEGE_LOCK = "PrivilegeLock"
    VOLITION_LOCK = "VolitionLock"
    INTEGRITY_LOCK = "IntegrityLock"
    CONSENT_LOCK = "ConsentLock"
    CAUTION_LOCK = "CautionLock"
    EVIDENCE_LOCK = "EvidenceLock"
    CONTINUITY_LOCK = "ContinuityLock"
    MAINTENANCE_LOCK = "MaintenanceLock"
    EMBODIMENT_LOCK = "EmbodimentLock"
    TRUST_LOCK = "TrustLock"
```

---

## 4.5 `EvidenceState`

```python
class EvidenceState(str, Enum):
    ASSERTED = "asserted"
    OBSERVED = "observed"
    WITNESSED = "witnessed"
    SIGNED = "signed"
    CHALLENGE_OPEN = "challenge_open"
    SETTLED = "settled"
    EXPIRED = "expired"
    CINEMATIC_ONLY = "cinematic_only"
```

---

## 4.6 `ChallengeStatus`

```python
class ChallengeStatus(str, Enum):
    OPEN = "open"
    QUEUED = "queued"
    UNDER_REVIEW = "under_review"
    RESOLVED_UPHOLD = "resolved_uphold"
    RESOLVED_MODIFY = "resolved_modify"
    RESOLVED_SPLIT = "resolved_split"
    DISMISSED = "dismissed"
    EXPIRED = "expired"
    ARCHIVED = "archived"
```

---

## 4.7 `ReviewOutcome`

```python
class ReviewOutcome(str, Enum):
    ANNOTATE = "annotate"
    RECLASSIFY = "reclassify"
    EVIDENCE_DOWNGRADE = "evidence_downgrade"
    EVIDENCE_UPGRADE = "evidence_upgrade"
    BRANCH_SPLIT = "branch_split"
    REOPENABILITY_CHANGE = "reopenability_change"
    SCOPE_RESTRICTION = "scope_restriction"
    UPHOLD = "uphold"
```

---

## 4.8 `ReopenabilityState`

```python
class ReopenabilityState(str, Enum):
    NOT_REOPENABLE = "not_reopenable"
    EVIDENCE_REQUIRED = "evidence_required"
    REVIEW_REQUIRED = "review_required"
    REOPENABLE = "reopenable"
```

---

## 4.9 `RenderMode`

```python
class RenderMode(str, Enum):
    NORMAL = "normal"
    AUDIT = "audit"
    PEDAGOGICAL = "pedagogical"
```

---

## 5. Foundational shared objects

## 5.1 `NodeRef`

```python
@dataclass(frozen=True)
class NodeRef:
    node_id: str
    node_kind: NodeKind
```

Minimal reference handle for graph, evidence, review, and storage cross-links.

---

## 5.2 `EdgeRef`

```python
@dataclass(frozen=True)
class EdgeRef:
    edge_id: str
    edge_kind: EdgeKind
```

---

## 5.3 `WitnessRef`

```python
@dataclass(frozen=True)
class WitnessRef:
    witness_id: str
    signing_class: str
    signed: bool
    envelope_ref: str | None = None
```

This object does **not** imply authority.
It only binds a visible object to an evidence carrier.

---

## 5.4 `TimeWindow`

```python
@dataclass
class TimeWindow:
    opened_ts: int
    deadline_ts: int
    kind: str
    is_open: bool
```

Can be reused for:
- challenge windows
- review windows
- bounded authority windows

---

## 6. Core status object

## 6.1 `StatusTuple`

```python
@dataclass
class StatusTuple:
    lane: Lane
    active: bool
    evidence_state: EvidenceState
    challenge_status: ChallengeStatus | None
    reopenability: ReopenabilityState | None
    expired: bool
    executable: bool
    render_mode_min: RenderMode = RenderMode.NORMAL
```

### Why this matters
This is the minimal state algebra carrier.

It answers:
- what kind of object this is,
- whether it is still active,
- how strong its evidence standing is,
- whether it is challenge-open,
- whether it can ever reopen,
- whether it is executable,
- and under what minimum mode it may be shown.

### Invariants
- `lane == CINEMATIC` -> `executable == False`
- `evidence_state == CINEMATIC_ONLY` -> `lane == CINEMATIC`
- `executable == True` -> `lane == RUNTIME`
- `expired == True` -> `evidence_state != SIGNED` unless historically preserved only
- `reopenability is not None` -> `lane in {RESEARCH, HISTORICAL}`

---

## 7. Runtime object family

## 7.1 `ExecutionNode`

```python
@dataclass
class ExecutionNode:
    node_id: str
    action_kind: str
    scope: str
    started_ts: int
    ended_ts: int | None
    actor_ref: str | None
    status: StatusTuple
    metadata: dict[str, Any]
```

### Role
Minimal projection of an actual executed or attempted runtime step.

### Important note
This is not a universal log row.
It is a typed view object over runtime truth.

---

## 7.2 `GlitchNode`

```python
@dataclass
class GlitchNode:
    node_id: str
    source_execution_ref: NodeRef
    lock_type: RuntimeLockType
    reason_code: str
    severity: str
    created_ts: int
    status: StatusTuple
    challenge_window: TimeWindow | None
    witness_ref: WitnessRef | None
    computed_hash: str | None
    stored_hash: str | None
    added_caps: list[str]
    removed_caps: list[str]
    rollback_reason: str | None
    metadata: dict[str, Any]
```

### Role
Typed projection of runtime collision with L4 or safety boundary.

### Canonical interpretation
A `GlitchNode` is **not** a bug report.
It is a first-class record that:
- runtime path collided with reality or boundary,
- speculative continuation is forbidden,
- and downstream review/research may proceed only under discipline.

### Key invariants
- `status.lane == Lane.RUNTIME`
- `status.executable == False`
- `lock_type` must be populated
- if `status.evidence_state in {WITNESSED, SIGNED, CHALLENGE_OPEN, SETTLED}` then `witness_ref is not None`

---

## 8. Research object family

## 8.1 `ResearchNode`

```python
@dataclass
class ResearchNode:
    node_id: str
    source_glitch_ref: NodeRef
    created_ts: int
    title: str
    summary: str
    missing_evidence: list[str]
    required_resources: list[str]
    reopenability: ReopenabilityState
    status: StatusTuple
    witness_ref: WitnessRef | None
    challenge_ref: str | None
    metadata: dict[str, Any]
```

### Role
Quarantined persistent object representing:
- what could not proceed,
- why it could not proceed,
- and what would be required to revisit it.

### Key invariants
- `status.lane == Lane.RESEARCH`
- `status.executable == False`
- `source_glitch_ref.node_kind == NodeKind.GLITCH_NODE`

---

## 8.2 `BackwardNode`

```python
@dataclass
class BackwardNode:
    node_id: str
    target_future_description: str
    source_research_ref: NodeRef
    gap_statement: str
    required_evidence: list[str]
    bridge_assumptions: list[str]
    status: StatusTuple
    metadata: dict[str, Any]
```

### Role
Directed research object that says:
- “this is the future state we wanted,”
- “this is the gap that prevented it,”
- “these are the assumptions that would need proof.”

### Key invariants
- `status.lane == Lane.RESEARCH`
- `status.executable == False`
- cannot exist without a `ResearchNode` relation

---

## 9. Evidence object family

## 9.1 `EvidenceBadge`

```python
@dataclass
class EvidenceBadge:
    evidence_state: EvidenceState
    signed: bool
    challengeable: bool
    expired: bool
    display_hint: str
```

### Role
Minimal render-facing evidence projection.

### Important note
This is a view helper, not the evidence itself.

---

## 9.2 `EvidenceRecord`

```python
@dataclass
class EvidenceRecord:
    evidence_id: str
    target_ref: NodeRef | EdgeRef
    evidence_state: EvidenceState
    roles: list[str]
    created_ts: int
    signer: str | None
    payload_hash: str | None
    witness_ref: WitnessRef | None
    expires_ts: int | None
    metadata: dict[str, Any]
```

### Role
Canonical typed evidence attachment.

### Key invariants
- `evidence_state == EvidenceState.SIGNED` -> `signer is not None`
- `evidence_state in {WITNESSED, SIGNED, CHALLENGE_OPEN, SETTLED}` -> `witness_ref is not None`

---

## 10. Review object family

## 10.1 `ChallengeRecord`

```python
@dataclass
class ChallengeRecord:
    challenge_id: str
    target_ref: NodeRef | EdgeRef
    opened_by_role: str
    opened_by_subject: str
    challenge_type: str
    reason: str
    opened_ts: int
    deadline_ts: int
    status: ChallengeStatus
    new_evidence_refs: list[str]
    metadata: dict[str, Any]
```

### Role
First-class dispute object.

### Key invariants
- `deadline_ts >= opened_ts`
- `status != None`
- target must be challengeable under rules

---

## 10.2 `ReviewRecord`

```python
@dataclass
class ReviewRecord:
    review_id: str
    challenge_ref: str
    reviewer_role: str
    reviewer_subject: str
    outcome: ReviewOutcome
    created_ts: int
    signed: bool
    witness_ref: WitnessRef | None
    previous_target_class: str | None
    new_target_class: str | None
    notes: str
    metadata: dict[str, Any]
```

### Role
Formal review outcome record.

### Key invariants
- `outcome == ReviewOutcome.RECLASSIFY` -> both class fields required
- `signed == True` -> `witness_ref is not None`

---

## 11. Guard object family

## 11.1 `TransitionGuard`

```python
@dataclass
class TransitionGuard:
    guard_id: str
    from_status: StatusTuple
    to_status: StatusTuple
    allowed: bool
    rule_code: str
    reason: str
```

### Role
First-class machine-readable result of transition legality checks.

### Example
A guard may deny:
- `ResearchNode` becoming executable
- `cinematic_only` becoming `signed`
- `challenge_open` becoming `settled` without a `ReviewRecord`

---

## 11.2 `ReopenabilityGate`

```python
@dataclass
class ReopenabilityGate:
    gate_id: str
    research_ref: NodeRef
    current_state: ReopenabilityState
    required_evidence: list[str]
    required_review: bool
    allowed: bool
    reason: str
```

### Role
Explicit gate object for moving from quarantined research toward legal re-entry for inspection or controlled reuse.

---

## 12. Graph/read object family

## 12.1 `GraphNodeView`

```python
@dataclass
class GraphNodeView:
    node_ref: NodeRef
    lane: Lane
    title: str
    label: str
    badge: EvidenceBadge
    challenge_status: ChallengeStatus | None
    render_mode_min: RenderMode
    visible: bool
    metadata: dict[str, Any]
```

### Role
Read-only projection for graph rendering.

### Important note
This object is derived from stateful truth.
It never creates authority.

---

## 12.2 `GraphEdgeView`

```python
@dataclass
class GraphEdgeView:
    edge_id: str
    edge_kind: EdgeKind
    source_ref: NodeRef
    target_ref: NodeRef
    badge: EvidenceBadge | None
    visible: bool
    metadata: dict[str, Any]
```

---

## 12.3 `GraphSlice`

```python
@dataclass
class GraphSlice:
    slice_id: str
    mode: RenderMode
    nodes: list[GraphNodeView]
    edges: list[GraphEdgeView]
    generated_ts: int
    integrity_root: str | None
```

### Role
Render/export unit for graph views.

### Key invariant
`integrity_root` may summarize the slice lineage,
but does not replace underlying witness records.

---

## 13. Relation grammar

Canonical relation pattern:

```text
ExecutionNode
  ->(collision) GlitchNode
  ->(derives_research) ResearchNode
  ->(needs_evidence) BackwardNode
  ->(witness_binds) EvidenceRecord / WitnessRef
  ->(challenge_opens) ChallengeRecord
  ->(review_resolves) ReviewRecord
  ->(cinematic_projects) GraphNodeView / GraphSlice
```

This relation order matters.

It prevents premature jump from:
runtime stop -> pretty future branch

without:
evidence, review, and explicit quarantine.

---

## 14. Forbidden object collapses

The following collapses are prohibited by design.

### 14.1 `ResearchNode` != executable task
No research object may be passed directly to runtime execution.

### 14.2 `EvidenceRecord` != legitimacy
Evidence may prove occurrence or integrity, not permission.

### 14.3 `GraphNodeView` != source of truth
Graph objects are read projections.

### 14.4 `BackwardNode` != promised roadmap
It expresses structured lack, not guaranteed future.

### 14.5 `ReviewRecord` != branch eraser
A review may modify interpretation but must preserve historical lineage.

---

## 15. Minimal JSON shapes

## 15.1 Example `GlitchNode`

```json
{
  "node_id": "glitch_01H...",
  "source_execution_ref": {"node_id": "exec_01H...", "node_kind": "ExecutionNode"},
  "lock_type": "PrivilegeLock",
  "reason_code": "scope_missing",
  "severity": "HIGH",
  "created_ts": 1775074000,
  "status": {
    "lane": "runtime",
    "active": true,
    "evidence_state": "witnessed",
    "challenge_status": "open",
    "reopenability": null,
    "expired": false,
    "executable": false,
    "render_mode_min": "normal"
  },
  "challenge_window": {
    "opened_ts": 1775074000,
    "deadline_ts": 1775077600,
    "kind": "challenge_review",
    "is_open": true
  },
  "witness_ref": {
    "witness_id": "wit_01H...",
    "signing_class": "entity_bound",
    "signed": true,
    "envelope_ref": "l4w_01H..."
  },
  "computed_hash": null,
  "stored_hash": null,
  "added_caps": [],
  "removed_caps": [],
  "rollback_reason": null,
  "metadata": {"route": "/dangerous/path"}
}
```

---

## 15.2 Example `ResearchNode`

```json
{
  "node_id": "research_01H...",
  "source_glitch_ref": {"node_id": "glitch_01H...", "node_kind": "GlitchNode"},
  "created_ts": 1775074010,
  "title": "Need explicit privilege proof for branch continuation",
  "summary": "Runtime path stopped at privilege boundary; future branch requires evidence-backed escalation.",
  "missing_evidence": ["signed escalation approval", "valid window_id"],
  "required_resources": ["review", "privilege token"],
  "reopenability": "evidence_required",
  "status": {
    "lane": "research",
    "active": true,
    "evidence_state": "asserted",
    "challenge_status": null,
    "reopenability": "evidence_required",
    "expired": false,
    "executable": false,
    "render_mode_min": "normal"
  },
  "witness_ref": null,
  "challenge_ref": null,
  "metadata": {}
}
```

---

## 15.3 Example `ChallengeRecord`

```json
{
  "challenge_id": "chg_01H...",
  "target_ref": {"node_id": "glitch_01H...", "node_kind": "GlitchNode"},
  "opened_by_role": "human_anchor",
  "opened_by_subject": "Owner",
  "challenge_type": "classification_dispute",
  "reason": "Insufficient basis for IntegrityLock classification",
  "opened_ts": 1775074100,
  "deadline_ts": 1775077700,
  "status": "under_review",
  "new_evidence_refs": [],
  "metadata": {}
}
```

---

## 16. Mapping to code-anatomy zones

### `GlitchNode`
Likely projected from:
- `modules/runtime/drift_quarantine.py`
- plus middleware refusal surfaces

### `ResearchNode` / `BackwardNode`
Likely stored through:
- `memory_manager.py`
- `modules/memory/chroma_adapter.py`

### `ChallengeRecord` / `ReviewRecord`
Likely live near:
- `drift_quarantine`
- `comm_window`
- future validator/rule gates

### `TransitionGuard`
Likely belongs near:
- `validator/*`
- `rules/*`

### `GraphNodeView` / `GraphEdgeView`
Likely assembled from:
- trace HTTP plugin
- memory flow HTTP plugin
- graph/read serializers

### `EvidenceRecord`
Likely anchored near:
- witness packet / integrity stack / Merkle layer

---

## 17. Recommended implementation order

1. define enums
2. define `StatusTuple`
3. define `GlitchNode`
4. define `ResearchNode`
5. define `ChallengeRecord`
6. define `ReviewRecord`
7. define `TransitionGuard`
8. define `EvidenceRecord`
9. define graph read objects
10. only then bind them to rendering

This order is not cosmetic.
It is anti-self-deception.

---

## 18. Explicit bridge

This pack turns the new stack from:
- layers,
- graphs,
- windows,
- and doctrines

into a first typed object language.

That is the explicit bridge between:
- conceptual architecture,
- file anatomy,
- and future executable code.

---

## 19. Hidden bridges

### Hidden Bridge 1 — Cybernetics
Typed objects increase regulator variety by separating:
collision,
research,
evidence,
review,
and display.

### Hidden Bridge 2 — Information Theory
Object typing reduces ambiguity and preserves lineage better than free-form narrative state.

---

## 20. Earth paragraph

In a serious machine, “alarm,” “work order,” “inspection seal,” “maintenance review,” and “dashboard icon” are not all the same object in a database. If they are modeled as one fuzzy blob, the machine may still run, but the first real failure will reveal that nobody can tell whether something actually broke, was merely suspected, was already inspected, or was only painted red on a screen. This pack exists to stop that kind of confusion before it enters the code.

---

## 21. Final position

`Object Model Draft Pack v0.1` is the first real typed spine for the new stack.

It does not yet implement the system.

But it does something just as important:

it makes it much harder for future implementation to cheat.
