"""Glitch Stack M1 contracts and anti-collapse guards.

M1 is deliberately modeled as a sidecar contract layer:

- runtime collision becomes a typed GlitchNode
- witnessed/challengeable evidence can derive a quarantined ResearchNode
- research and cinematic lanes cannot silently become runtime truth

Nothing here scans memory, touches sacred stores, or mutates live runtime state.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


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


class ReopenabilityState(str, Enum):
    NOT_REOPENABLE = "not_reopenable"
    EVIDENCE_REQUIRED = "evidence_required"
    REVIEW_REQUIRED = "review_required"
    REOPENABLE = "reopenable"


class RenderMode(str, Enum):
    CANONICAL = "canonical"
    GRAPH = "graph"
    CINEMATIC = "cinematic"


@dataclass(frozen=True)
class NodeRef:
    id: str
    kind: NodeKind
    lane: Lane


@dataclass(frozen=True)
class WitnessRef:
    witness_id: str
    witness_kind: str = "local"
    signature_ref: str | None = None


@dataclass(frozen=True)
class TimeWindow:
    opened_at: str
    closes_at: str | None = None
    policy: str = "challenge"


@dataclass(frozen=True)
class StatusTuple:
    lane: Lane
    evidence_state: EvidenceState = EvidenceState.ASSERTED
    executable: bool = False
    reopenability: ReopenabilityState | None = None
    render_mode: RenderMode = RenderMode.CANONICAL


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    state: EvidenceState
    witness_ref: WitnessRef | None = None
    signer: str | None = None
    payload_hash: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationIssue:
    rule_code: str
    message: str
    severity: str = "error"
    layer: str = "glitch_m1"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _to_primitive(self)


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    rule_code: str
    message: str
    severity: str = "info"
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(
        cls,
        rule_code: str = "allowed",
        message: str = "Transition allowed.",
        **details: Any,
    ) -> "GuardDecision":
        return cls(True, rule_code, message, "info", details)

    @classmethod
    def deny(
        cls,
        rule_code: str,
        message: str,
        severity: str = "error",
        **details: Any,
    ) -> "GuardDecision":
        return cls(False, rule_code, message, severity, details)

    def to_dict(self) -> dict[str, Any]:
        return _to_primitive(self)


@dataclass(frozen=True)
class GlitchNode:
    node_ref: NodeRef
    collision_id: str
    lock_type: RuntimeLockType
    status: StatusTuple
    evidence_records: tuple[EvidenceRecord, ...] = ()
    witness_ref: WitnessRef | None = None
    challenge_window: TimeWindow | None = None
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchNode:
    node_ref: NodeRef
    source_glitch_ref: NodeRef
    status: StatusTuple
    summary: str
    evidence_refs: tuple[str, ...] = ()
    challenge_window: TimeWindow | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalEvent:
    event_type: str
    event_id: str
    occurred_at: str
    subject_ref: NodeRef
    payload: dict[str, Any] = field(default_factory=dict)


class GlitchValidationError(ValueError):
    """Raised when a reducer would create an invalid Glitch M1 object."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{issue.rule_code}: {issue.message}" for issue in issues))


WITNESS_REQUIRED_STATES = {
    EvidenceState.WITNESSED,
    EvidenceState.SIGNED,
    EvidenceState.CHALLENGE_OPEN,
    EvidenceState.SETTLED,
}


def register_runtime_collision(
    *,
    collision_id: str,
    lock_type: RuntimeLockType,
    summary: str = "",
    node_id: str | None = None,
    occurred_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[GlitchNode, tuple[CanonicalEvent, ...]]:
    """Create a runtime GlitchNode from an explicit collision signal."""

    ts = occurred_at or _now_iso()
    node_ref = NodeRef(node_id or f"glitch:{collision_id}", NodeKind.GLITCH_NODE, Lane.RUNTIME)
    glitch = GlitchNode(
        node_ref=node_ref,
        collision_id=collision_id,
        lock_type=lock_type,
        status=StatusTuple(lane=Lane.RUNTIME, executable=False),
        summary=summary,
        metadata=dict(metadata or {}),
    )
    _raise_if_invalid(validate_glitch_node(glitch))
    events = (
        CanonicalEvent(
            event_type="RuntimeCollisionRegistered",
            event_id=_event_id("runtime-collision"),
            occurred_at=ts,
            subject_ref=node_ref,
            payload={"collision_id": collision_id, "lock_type": lock_type.value},
        ),
        CanonicalEvent(
            event_type="GlitchNodeCreated",
            event_id=_event_id("glitch-node"),
            occurred_at=ts,
            subject_ref=node_ref,
            payload={"collision_id": collision_id},
        ),
    )
    return glitch, events


def attach_collision_witness(
    glitch: GlitchNode,
    witness_ref: WitnessRef,
    *,
    evidence_state: EvidenceState = EvidenceState.WITNESSED,
    evidence_id: str | None = None,
    signer: str | None = None,
    payload_hash: str | None = None,
    occurred_at: str | None = None,
    details: dict[str, Any] | None = None,
) -> tuple[GlitchNode, CanonicalEvent]:
    """Attach witness-backed evidence to a GlitchNode."""

    record = EvidenceRecord(
        evidence_id=evidence_id or f"evidence:{uuid4().hex}",
        state=evidence_state,
        witness_ref=witness_ref,
        signer=signer,
        payload_hash=payload_hash,
        details=dict(details or {}),
    )
    updated = replace(
        glitch,
        witness_ref=witness_ref,
        evidence_records=(*glitch.evidence_records, record),
        status=replace(glitch.status, evidence_state=evidence_state),
    )
    _raise_if_invalid(validate_glitch_node(updated))
    event = CanonicalEvent(
        event_type="CollisionWitnessAttached",
        event_id=_event_id("collision-witness"),
        occurred_at=occurred_at or _now_iso(),
        subject_ref=updated.node_ref,
        payload={
            "evidence_id": record.evidence_id,
            "evidence_state": evidence_state.value,
            "witness_id": witness_ref.witness_id,
        },
    )
    return updated, event


def open_collision_challenge_window(
    glitch: GlitchNode,
    window: TimeWindow,
    *,
    occurred_at: str | None = None,
) -> tuple[GlitchNode, CanonicalEvent]:
    """Open a challenge window for a witnessed runtime collision."""

    updated = replace(
        glitch,
        challenge_window=window,
        status=replace(glitch.status, evidence_state=EvidenceState.CHALLENGE_OPEN),
    )
    _raise_if_invalid(validate_glitch_node(updated))
    event = CanonicalEvent(
        event_type="ChallengeOpened",
        event_id=_event_id("challenge"),
        occurred_at=occurred_at or _now_iso(),
        subject_ref=updated.node_ref,
        payload={"opened_at": window.opened_at, "closes_at": window.closes_at},
    )
    return updated, event


def derive_research_node(
    glitch: GlitchNode,
    *,
    summary: str,
    node_id: str | None = None,
    reopenability: ReopenabilityState = ReopenabilityState.EVIDENCE_REQUIRED,
    occurred_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[ResearchNode, CanonicalEvent]:
    """Derive a quarantined research lane node from a valid GlitchNode."""

    _raise_if_invalid(validate_glitch_node(glitch))
    if glitch.witness_ref is None or not glitch.evidence_records:
        raise GlitchValidationError(
            [
                ValidationIssue(
                    "RESEARCH_WITNESS_REQUIRED",
                    "A ResearchNode may only be derived from witnessed glitch evidence.",
                )
            ]
        )

    node_ref = NodeRef(
        node_id or f"research:{glitch.collision_id}",
        NodeKind.RESEARCH_NODE,
        Lane.RESEARCH,
    )
    research = ResearchNode(
        node_ref=node_ref,
        source_glitch_ref=glitch.node_ref,
        status=StatusTuple(
            lane=Lane.RESEARCH,
            evidence_state=glitch.status.evidence_state,
            executable=False,
            reopenability=reopenability,
        ),
        summary=summary,
        evidence_refs=tuple(record.evidence_id for record in glitch.evidence_records),
        challenge_window=glitch.challenge_window,
        metadata={"source_collision_id": glitch.collision_id, **dict(metadata or {})},
    )
    _raise_if_invalid(validate_research_node(research))
    event = CanonicalEvent(
        event_type="ResearchNodeDerived",
        event_id=_event_id("research-node"),
        occurred_at=occurred_at or _now_iso(),
        subject_ref=node_ref,
        payload={
            "source_glitch_id": glitch.node_ref.id,
            "evidence_refs": list(research.evidence_refs),
        },
    )
    return research, event


def store_research_node(research_node: ResearchNode, root: str | Path) -> Path:
    """Persist a ResearchNode below an explicit caller-provided sidecar root."""

    _raise_if_invalid(validate_research_node(research_node))
    root_path = Path(root)
    node_dir = root_path / "research_nodes"
    node_dir.mkdir(parents=True, exist_ok=True)
    target = node_dir / f"{_safe_file_id(research_node.node_ref.id)}.json"
    tmp = target.with_name(f"{target.name}.{uuid4().hex}.tmp")
    payload = json.dumps(_to_primitive(research_node), ensure_ascii=False, sort_keys=True, indent=2)
    tmp.write_text(payload + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


def to_record(value: Any) -> Any:
    """Convert Glitch M1 dataclasses/enums into JSON-compatible records."""

    return _to_primitive(value)


def validate_status_tuple(status: StatusTuple) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if status.lane == Lane.CINEMATIC and status.executable:
        issues.append(
            ValidationIssue(
                "STATUS_CINEMATIC_EXECUTABLE",
                "Cinematic lane objects cannot be executable.",
            )
        )
    if status.evidence_state == EvidenceState.CINEMATIC_ONLY and status.lane != Lane.CINEMATIC:
        issues.append(
            ValidationIssue(
                "STATUS_CINEMATIC_ONLY_LANE",
                "cinematic_only evidence must remain on the cinematic lane.",
            )
        )
    if status.executable and status.lane != Lane.RUNTIME:
        issues.append(
            ValidationIssue(
                "STATUS_EXECUTABLE_NOT_RUNTIME",
                "Only runtime lane objects can be executable.",
            )
        )
    if status.reopenability is not None and status.lane not in {Lane.RESEARCH, Lane.HISTORICAL}:
        issues.append(
            ValidationIssue(
                "STATUS_REOPENABILITY_LANE",
                "Reopenability belongs to research or historical lanes.",
            )
        )
    return issues


def validate_glitch_node(glitch: GlitchNode) -> list[ValidationIssue]:
    issues = validate_status_tuple(glitch.status)
    if glitch.node_ref.kind != NodeKind.GLITCH_NODE:
        issues.append(ValidationIssue("GLITCH_KIND_INVALID", "GlitchNode has wrong node kind."))
    if glitch.node_ref.lane != Lane.RUNTIME or glitch.status.lane != Lane.RUNTIME:
        issues.append(ValidationIssue("GLITCH_LANE_NOT_RUNTIME", "GlitchNode must stay runtime-lane."))
    if glitch.status.executable:
        issues.append(ValidationIssue("GLITCH_EXECUTABLE", "GlitchNode must never be executable."))
    if glitch.lock_type is None:
        issues.append(ValidationIssue("GLITCH_LOCK_REQUIRED", "GlitchNode requires a runtime lock type."))
    if glitch.status.evidence_state in WITNESS_REQUIRED_STATES and glitch.witness_ref is None:
        issues.append(
            ValidationIssue(
                "GLITCH_WITNESS_REQUIRED",
                "Witnessed, signed, challenged, or settled GlitchNode evidence requires a witness.",
            )
        )
    if glitch.status.evidence_state == EvidenceState.CHALLENGE_OPEN and glitch.challenge_window is None:
        issues.append(
            ValidationIssue(
                "GLITCH_CHALLENGE_WINDOW_REQUIRED",
                "challenge_open evidence requires a challenge window.",
            )
        )
    return issues


def validate_research_node(research: ResearchNode) -> list[ValidationIssue]:
    issues = validate_status_tuple(research.status)
    if research.node_ref.kind != NodeKind.RESEARCH_NODE:
        issues.append(ValidationIssue("RESEARCH_KIND_INVALID", "ResearchNode has wrong node kind."))
    if research.node_ref.lane != Lane.RESEARCH or research.status.lane != Lane.RESEARCH:
        issues.append(
            ValidationIssue("RESEARCH_LANE_NOT_RESEARCH", "ResearchNode must stay research-lane.")
        )
    if research.status.executable:
        issues.append(ValidationIssue("RESEARCH_EXECUTABLE", "ResearchNode must never be executable."))
    if research.source_glitch_ref.kind != NodeKind.GLITCH_NODE:
        issues.append(
            ValidationIssue(
                "RESEARCH_SOURCE_NOT_GLITCH",
                "ResearchNode source must be a GlitchNode reference.",
            )
        )
    if research.status.reopenability is None:
        issues.append(
            ValidationIssue(
                "RESEARCH_REOPENABILITY_REQUIRED",
                "ResearchNode must carry explicit reopenability state.",
            )
        )
    return issues


def validate_transition(source: StatusTuple, target: StatusTuple) -> GuardDecision:
    """Validate cross-lane authority transitions for M1 anti-collapse rules."""

    if source.lane == Lane.RESEARCH and target.lane == Lane.RUNTIME:
        return GuardDecision.deny(
            "TRANSITION_RESEARCH_TO_RUNTIME_FORBIDDEN",
            "Research lane cannot become runtime truth by direct transition.",
        )
    if source.lane == Lane.RESEARCH and target.executable:
        return GuardDecision.deny(
            "TRANSITION_RESEARCH_EXECUTABLE_FORBIDDEN",
            "Research lane cannot become executable by shortcut.",
        )
    if source.lane == Lane.CINEMATIC and target.lane == Lane.RUNTIME:
        return GuardDecision.deny(
            "TRANSITION_CINEMATIC_TO_RUNTIME_FORBIDDEN",
            "Cinematic projection cannot create runtime authority.",
        )
    source_issues = validate_status_tuple(source)
    target_issues = validate_status_tuple(target)
    if source_issues or target_issues:
        return GuardDecision.deny(
            "TRANSITION_STATUS_INVALID",
            "Transition includes invalid status tuple.",
            issues=[issue.to_dict() for issue in [*source_issues, *target_issues]],
        )
    return GuardDecision.allow()


def authorize_runtime_from_evidence(evidence: EvidenceRecord) -> GuardDecision:
    """Return whether evidence alone may authorize runtime execution.

    A signature is useful evidence, but it is not legitimacy. Only settled,
    witnessed evidence can be used by later layers as a possible runtime input.
    """

    if evidence.state == EvidenceState.SIGNED:
        return GuardDecision.deny(
            "SIGNATURE_NOT_LEGITIMACY",
            "A signature is evidence, not runtime legitimacy.",
            evidence_id=evidence.evidence_id,
        )
    if evidence.state == EvidenceState.SETTLED and evidence.witness_ref is not None:
        return GuardDecision.allow(
            "SETTLED_WITNESSED_EVIDENCE",
            "Settled witnessed evidence may be considered by later runtime guards.",
            evidence_id=evidence.evidence_id,
        )
    return GuardDecision.deny(
        "EVIDENCE_NOT_RUNTIME_AUTHORITY",
        "Evidence is not sufficient runtime authority.",
        evidence_id=evidence.evidence_id,
        evidence_state=evidence.state.value,
    )


def _raise_if_invalid(issues: list[ValidationIssue]) -> None:
    if issues:
        raise GlitchValidationError(issues)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _event_id(prefix: str) -> str:
    return f"{prefix}:{uuid4().hex}"


def _safe_file_id(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in ("-", "_", "."):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("._") or "research_node"


def _to_primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _to_primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_primitive(item) for item in value]
    return value
