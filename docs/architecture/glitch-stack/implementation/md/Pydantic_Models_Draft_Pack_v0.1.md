# Pydantic Models Draft Pack v0.1

**Status:** Draft code pack  
**Scope:** Pydantic v2-oriented model draft for the new stack  
**Purpose:** Provide a concrete Python model layer that can later be adapted into `ester-clean-code` without collapsing the distinctions established in the conceptual, schema, semantic, and transition packs.

**Assumptions**
- Python 3.11+
- Pydantic v2
- `ConfigDict(extra="forbid")`
- runtime truth remains below graph/read projections
- evidence never implies authority
- research remains quarantined
- review preserves lineage

---

## 1. Package intent

This pack is not the final implementation.

It is a **code-shaped draft spine** for:

- enums
- shared primitives
- status object
- runtime node family
- research node family
- evidence and review family
- graph/read family
- transition guard family

The goal is to remove ambiguity early enough that future implementation cannot quietly flatten:
- runtime truth,
- research quarantine,
- witness evidence,
- review lineage,
- and graph projection

into one fuzzy blob.

---

## 2. Suggested package layout

```text
models/
  __init__.py
  enums.py
  common.py
  status.py
  runtime.py
  research.py
  evidence.py
  review.py
  graph.py
  guards.py
```

This document shows one-file draft code for clarity.
The real code may split later.

---

## 3. Draft code

```python
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ============================================================================
# ENUMS
# ============================================================================

class Lane(str, Enum):
    RUNTIME = "runtime"
    RESEARCH = "research"
    WITNESS = "witness"
    HISTORICAL = "historical"
    CINEMATIC = "cinematic"


class NodeKind(str, Enum):
    EXECUTION_NODE = "ExecutionNode"
    GLITCH_NODE = "GlitchNode"
    RESEARCH_NODE = "ResearchNode"
    BACKWARD_NODE = "BackwardNode"
    WITNESS_NODE = "WitnessNode"
    REVIEW_NODE = "ReviewNode"
    GRAPH_VIEW_NODE = "GraphViewNode"


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


class EvidenceState(str, Enum):
    ASSERTED = "asserted"
    OBSERVED = "observed"
    WITNESSED = "witnessed"
    SIGNED = "signed"
    CHALLENGE_OPEN = "challenge_open"
    SETTLED = "settled"
    EXPIRED = "expired"
    CINEMATIC_ONLY = "cinematic_only"


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


class ReviewOutcome(str, Enum):
    ANNOTATE = "annotate"
    RECLASSIFY = "reclassify"
    EVIDENCE_DOWNGRADE = "evidence_downgrade"
    EVIDENCE_UPGRADE = "evidence_upgrade"
    BRANCH_SPLIT = "branch_split"
    REOPENABILITY_CHANGE = "reopenability_change"
    SCOPE_RESTRICTION = "scope_restriction"
    UPHOLD = "uphold"


class ReopenabilityState(str, Enum):
    NOT_REOPENABLE = "not_reopenable"
    EVIDENCE_REQUIRED = "evidence_required"
    REVIEW_REQUIRED = "review_required"
    REOPENABLE = "reopenable"


class RenderMode(str, Enum):
    NORMAL = "normal"
    AUDIT = "audit"
    PEDAGOGICAL = "pedagogical"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TransitionClass(str, Enum):
    LEGAL = "LEGAL"
    CONDITIONAL = "CONDITIONAL"
    FORBIDDEN = "FORBIDDEN"


# ============================================================================
# BASE
# ============================================================================

class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        populate_by_name=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )


# ============================================================================
# COMMON PRIMITIVES
# ============================================================================

class NodeRef(StrictModel):
    node_id: str = Field(min_length=1)
    node_kind: NodeKind


class EdgeRef(StrictModel):
    edge_id: str = Field(min_length=1)
    edge_kind: EdgeKind


class WitnessRef(StrictModel):
    witness_id: str = Field(min_length=1)
    signing_class: str = Field(min_length=1)
    signed: bool
    envelope_ref: str | None = None


class TimeWindow(StrictModel):
    opened_ts: int = Field(ge=0)
    deadline_ts: int = Field(ge=0)
    kind: str = Field(min_length=1)
    is_open: bool

    @model_validator(mode="after")
    def validate_deadline(self) -> "TimeWindow":
        if self.deadline_ts < self.opened_ts:
            raise ValueError("SEM_TIMEWINDOW_DEADLINE_INVALID")
        return self


# ============================================================================
# STATUS
# ============================================================================

class StatusTuple(StrictModel):
    lane: Lane
    active: bool
    evidence_state: EvidenceState
    challenge_status: ChallengeStatus | None = None
    reopenability: ReopenabilityState | None = None
    expired: bool
    executable: bool
    render_mode_min: RenderMode = RenderMode.NORMAL

    @model_validator(mode="after")
    def validate_status_semantics(self) -> "StatusTuple":
        if self.lane == Lane.CINEMATIC and self.executable:
            raise ValueError("SEM_CINEMATIC_EXECUTABLE_FORBIDDEN")

        if self.evidence_state == EvidenceState.CINEMATIC_ONLY and self.lane != Lane.CINEMATIC:
            raise ValueError("SEM_CINEMATIC_STATE_LANE_MISMATCH")

        if self.executable and self.lane != Lane.RUNTIME:
            raise ValueError("SEM_EXECUTABLE_LANE_FORBIDDEN")

        if self.reopenability is not None and self.lane not in {Lane.RESEARCH, Lane.HISTORICAL}:
            raise ValueError("SEM_REOPENABILITY_LANE_FORBIDDEN")

        if self.challenge_status is not None and self.evidence_state not in {
            EvidenceState.WITNESSED,
            EvidenceState.SIGNED,
            EvidenceState.CHALLENGE_OPEN,
            EvidenceState.SETTLED,
            EvidenceState.EXPIRED,
        }:
            raise ValueError("SEM_CHALLENGE_EVIDENCE_MISMATCH")

        if self.expired and self.executable:
            raise ValueError("SEM_EXPIRED_EXECUTABLE_FORBIDDEN")

        return self


# ============================================================================
# RUNTIME FAMILY
# ============================================================================

class ExecutionNode(StrictModel):
    node_id: str = Field(min_length=1)
    action_kind: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    started_ts: int = Field(ge=0)
    ended_ts: int | None = Field(default=None, ge=0)
    actor_ref: str | None = None
    status: StatusTuple
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_execution_node(self) -> "ExecutionNode":
        if self.status.lane != Lane.RUNTIME:
            raise ValueError("SEM_EXECUTIONNODE_NONRUNTIME_LANE")
        if self.status.evidence_state == EvidenceState.CINEMATIC_ONLY:
            raise ValueError("SEM_EXECUTIONNODE_CINEMATIC_ONLY_FORBIDDEN")
        if self.ended_ts is not None and self.ended_ts < self.started_ts:
            raise ValueError("SEM_EXECUTIONNODE_TIME_ORDER_INVALID")
        return self


class GlitchNode(StrictModel):
    node_id: str = Field(min_length=1)
    source_execution_ref: NodeRef
    lock_type: RuntimeLockType
    reason_code: str = Field(min_length=1)
    severity: Severity
    created_ts: int = Field(ge=0)
    status: StatusTuple
    challenge_window: TimeWindow | None = None
    witness_ref: WitnessRef | None = None
    computed_hash: str | None = None
    stored_hash: str | None = None
    added_caps: list[str] = Field(default_factory=list)
    removed_caps: list[str] = Field(default_factory=list)
    rollback_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_glitch_node(self) -> "GlitchNode":
        if self.source_execution_ref.node_kind != NodeKind.EXECUTION_NODE:
            raise ValueError("SEM_GLITCH_SOURCE_KIND_INVALID")
        if self.status.lane != Lane.RUNTIME:
            raise ValueError("SEM_GLITCH_NONRUNTIME_LANE")
        if self.status.executable:
            raise ValueError("SEM_GLITCH_EXECUTABLE_FORBIDDEN")
        if self.status.evidence_state in {
            EvidenceState.WITNESSED,
            EvidenceState.SIGNED,
            EvidenceState.CHALLENGE_OPEN,
            EvidenceState.SETTLED,
        } and self.witness_ref is None:
            raise ValueError("SEM_GLITCH_WITNESS_REQUIRED")
        if self.status.challenge_status is not None and self.challenge_window is None:
            raise ValueError("SEM_GLITCH_CHALLENGE_WINDOW_REQUIRED")
        return self


# ============================================================================
# RESEARCH FAMILY
# ============================================================================

class ResearchNode(StrictModel):
    node_id: str = Field(min_length=1)
    source_glitch_ref: NodeRef
    created_ts: int = Field(ge=0)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    missing_evidence: list[str] = Field(default_factory=list)
    required_resources: list[str] = Field(default_factory=list)
    reopenability: ReopenabilityState
    status: StatusTuple
    witness_ref: WitnessRef | None = None
    challenge_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_research_node(self) -> "ResearchNode":
        if self.source_glitch_ref.node_kind != NodeKind.GLITCH_NODE:
            raise ValueError("SEM_RESEARCH_SOURCE_KIND_INVALID")
        if self.status.lane != Lane.RESEARCH:
            raise ValueError("SEM_RESEARCH_NONRESEARCH_LANE")
        if self.status.executable:
            raise ValueError("SEM_RESEARCH_EXECUTABLE_FORBIDDEN")
        if self.status.reopenability is None:
            raise ValueError("SEM_RESEARCH_REOPENABILITY_REQUIRED")
        return self


class BackwardNode(StrictModel):
    node_id: str = Field(min_length=1)
    target_future_description: str = Field(min_length=1)
    source_research_ref: NodeRef
    gap_statement: str = Field(min_length=1)
    required_evidence: list[str] = Field(default_factory=list)
    bridge_assumptions: list[str] = Field(default_factory=list)
    status: StatusTuple
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_backward_node(self) -> "BackwardNode":
        if self.source_research_ref.node_kind != NodeKind.RESEARCH_NODE:
            raise ValueError("SEM_BACKWARD_SOURCE_KIND_INVALID")
        if self.status.lane != Lane.RESEARCH:
            raise ValueError("SEM_BACKWARD_NONRESEARCH_LANE")
        if self.status.executable:
            raise ValueError("SEM_BACKWARD_EXECUTABLE_FORBIDDEN")
        return self


# ============================================================================
# EVIDENCE FAMILY
# ============================================================================

class EvidenceBadge(StrictModel):
    evidence_state: EvidenceState
    signed: bool
    challengeable: bool
    expired: bool
    display_hint: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_badge(self) -> "EvidenceBadge":
        if self.evidence_state == EvidenceState.SIGNED and not self.signed:
            raise ValueError("SEM_BADGE_SIGNED_FLAG_MISMATCH")
        if self.evidence_state == EvidenceState.EXPIRED and not self.expired:
            raise ValueError("SEM_BADGE_EXPIRED_FLAG_MISMATCH")
        return self


class EvidenceRecord(StrictModel):
    evidence_id: str = Field(min_length=1)
    target_ref: NodeRef | EdgeRef
    evidence_state: EvidenceState
    roles: list[str] = Field(default_factory=list)
    created_ts: int = Field(ge=0)
    signer: str | None = None
    payload_hash: str | None = None
    witness_ref: WitnessRef | None = None
    expires_ts: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence_record(self) -> "EvidenceRecord":
        if self.evidence_state == EvidenceState.SIGNED and self.signer is None:
            raise ValueError("SEM_EVIDENCE_SIGNER_REQUIRED")

        if self.evidence_state in {
            EvidenceState.WITNESSED,
            EvidenceState.SIGNED,
            EvidenceState.CHALLENGE_OPEN,
            EvidenceState.SETTLED,
        } and self.witness_ref is None:
            raise ValueError("SEM_EVIDENCE_WITNESS_REF_REQUIRED")

        if self.evidence_state == EvidenceState.CINEMATIC_ONLY:
            if isinstance(self.target_ref, NodeRef) and self.target_ref.node_kind != NodeKind.GRAPH_VIEW_NODE:
                raise ValueError("SEM_EVIDENCE_CINEMATIC_TARGET_FORBIDDEN")
        return self


# ============================================================================
# REVIEW FAMILY
# ============================================================================

class ChallengeRecord(StrictModel):
    challenge_id: str = Field(min_length=1)
    target_ref: NodeRef | EdgeRef
    opened_by_role: str = Field(min_length=1)
    opened_by_subject: str = Field(min_length=1)
    challenge_type: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    opened_ts: int = Field(ge=0)
    deadline_ts: int = Field(ge=0)
    status: ChallengeStatus
    new_evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_challenge_record(self) -> "ChallengeRecord":
        if self.deadline_ts < self.opened_ts:
            raise ValueError("SEM_CHALLENGE_DEADLINE_INVALID")
        return self


class ReviewRecord(StrictModel):
    review_id: str = Field(min_length=1)
    challenge_ref: str = Field(min_length=1)
    reviewer_role: str = Field(min_length=1)
    reviewer_subject: str = Field(min_length=1)
    outcome: ReviewOutcome
    created_ts: int = Field(ge=0)
    signed: bool
    witness_ref: WitnessRef | None = None
    previous_target_class: str | None = None
    new_target_class: str | None = None
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_review_record(self) -> "ReviewRecord":
        if self.outcome == ReviewOutcome.RECLASSIFY:
            if not self.previous_target_class or not self.new_target_class:
                raise ValueError("SEM_REVIEW_RECLASS_FIELDS_REQUIRED")

        if self.signed and self.witness_ref is None:
            raise ValueError("SEM_REVIEW_SIGNED_WITNESS_REQUIRED")

        if self.outcome == ReviewOutcome.BRANCH_SPLIT:
            if not self.metadata.get("split_lineage_ref"):
                raise ValueError("SEM_REVIEW_SPLIT_LINEAGE_REQUIRED")

        return self


# ============================================================================
# GUARDS
# ============================================================================

class TransitionGuard(StrictModel):
    guard_id: str = Field(min_length=1)
    from_status: StatusTuple
    to_status: StatusTuple
    allowed: bool
    transition_class: TransitionClass
    rule_code: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    required_conditions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_transition_guard(self) -> "TransitionGuard":
        if not self.allowed and not self.reason:
            raise ValueError("SEM_GUARD_REASON_REQUIRED")

        if self.transition_class == TransitionClass.FORBIDDEN and self.allowed:
            raise ValueError("SEM_GUARD_SHORTCUT_INVALID")

        return self


class ReopenabilityGate(StrictModel):
    gate_id: str = Field(min_length=1)
    research_ref: NodeRef
    current_state: ReopenabilityState
    required_evidence: list[str] = Field(default_factory=list)
    required_review: bool
    allowed: bool
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_reopenability_gate(self) -> "ReopenabilityGate":
        if self.research_ref.node_kind != NodeKind.RESEARCH_NODE:
            raise ValueError("SEM_GATE_SOURCE_KIND_INVALID")
        return self


# ============================================================================
# GRAPH / READ FAMILY
# ============================================================================

class GraphNodeView(StrictModel):
    node_ref: NodeRef
    lane: Lane
    title: str = Field(min_length=1)
    label: str = Field(min_length=1)
    badge: EvidenceBadge
    challenge_status: ChallengeStatus | None = None
    render_mode_min: RenderMode
    visible: bool
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph_node(self) -> "GraphNodeView":
        if self.lane == Lane.RUNTIME and self.badge.evidence_state == EvidenceState.CINEMATIC_ONLY:
            raise ValueError("SEM_GRAPH_LANE_BADGE_MISMATCH")
        if "executable" in self.metadata:
            raise ValueError("SEM_GRAPH_EXECUTABLE_FIELD_FORBIDDEN")
        return self


class GraphEdgeView(StrictModel):
    edge_id: str = Field(min_length=1)
    edge_kind: EdgeKind
    source_ref: NodeRef
    target_ref: NodeRef
    badge: EvidenceBadge | None = None
    visible: bool
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph_edge(self) -> "GraphEdgeView":
        if self.edge_kind == EdgeKind.CINEMATIC_PROJECTS:
            if self.metadata.get("retyped_as") in {
                EdgeKind.EXECUTION_FLOW.value,
                EdgeKind.REVIEW_RESOLVES.value,
                EdgeKind.WITNESS_BINDS.value,
            }:
                raise ValueError("SEM_GRAPH_EDGE_LAUNDERING_FORBIDDEN")
        return self


class GraphSlice(StrictModel):
    slice_id: str = Field(min_length=1)
    mode: RenderMode
    nodes: list[GraphNodeView] = Field(default_factory=list)
    edges: list[GraphEdgeView] = Field(default_factory=list)
    generated_ts: int = Field(ge=0)
    integrity_root: str | None = None

    @model_validator(mode="after")
    def validate_graph_slice(self) -> "GraphSlice":
        if self.mode == RenderMode.AUDIT and self.integrity_root is None:
            # notice-level concern in conceptual packs; here we keep object valid
            self.metadata_notice()
        return self

    def metadata_notice(self) -> None:
        # placeholder hook for non-fatal audit warnings
        return


# ============================================================================
# OPTIONAL: SEMANTIC VALIDATION RESULT
# ============================================================================

class SemanticValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    NOTICE = "notice"


class SemanticValidationResult(StrictModel):
    ok: bool
    layer: Literal["semantic"] = "semantic"
    rule_code: str = Field(min_length=1)
    severity: SemanticValidationSeverity
    message: str = Field(min_length=1)
    target_ref: NodeRef | EdgeRef | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    hint: str | None = None


# ============================================================================
# OPTIONAL: MACHINE-FRIENDLY PACK EXPORT EXAMPLE
# ============================================================================

__all__ = [
    "Lane",
    "NodeKind",
    "EdgeKind",
    "RuntimeLockType",
    "EvidenceState",
    "ChallengeStatus",
    "ReviewOutcome",
    "ReopenabilityState",
    "RenderMode",
    "Severity",
    "TransitionClass",
    "NodeRef",
    "EdgeRef",
    "WitnessRef",
    "TimeWindow",
    "StatusTuple",
    "ExecutionNode",
    "GlitchNode",
    "ResearchNode",
    "BackwardNode",
    "EvidenceBadge",
    "EvidenceRecord",
    "ChallengeRecord",
    "ReviewRecord",
    "TransitionGuard",
    "ReopenabilityGate",
    "GraphNodeView",
    "GraphEdgeView",
    "GraphSlice",
    "SemanticValidationResult",
]
```

---

## 4. Implementation notes

### 4.1 Why Pydantic v2
Because we want:
- explicit validators,
- strict field control,
- future JSON Schema emission,
- and easy bridge to API/storage layers.

### 4.2 Why validators are still inside models
Because this pack is a **draft spine**.
Later, some checks may migrate outward into:
- semantic validator layer,
- transition reducer layer,
- integrity validator layer.

But at draft stage, embedding key invariants prevents immediate cheating.

### 4.3 What should stay out of these models
Do **not** bake in:
- database adapters,
- route handlers,
- graph rendering logic,
- cryptographic verification routines,
- reducer state machines.

These models should remain:
**typed carriers + first-line coherence checks**.

---

## 5. Explicit bridge

This pack is the code-facing bridge between:

- conceptual layers,
- schema contract,
- semantic rules,
- transition legality,
- and future `ester-clean-code` integration.

It translates architecture into Python objects that can actually be imported, validated, serialized, and tested.

---

## 6. Hidden bridges

### Hidden Bridge 1 — Cybernetics
The pack preserves regulator differentiation:
runtime stop,
research quarantine,
evidence standing,
review lineage,
and display projection remain different organs.

### Hidden Bridge 2 — Information Theory
Typed models reduce ambiguity and force category separation before state starts flowing.

---

## 7. Earth paragraph

In a real control cabinet, the relay, the fault record, the signed inspection, the maintenance window, and the lamp on the panel may all concern the same incident — but they do not share one terminal block. If you wire them together as if they were one thing, the cabinet becomes easier to draw and harder to trust. These models exist to keep the wiring honest.

---

## 8. Final position

`Pydantic Models Draft Pack v0.1` is not yet the system.

But it is already something important:
a point where future code will have to choose between fidelity and cheating.

That is a very good place to be.
