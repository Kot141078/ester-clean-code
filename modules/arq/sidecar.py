"""ARQ profile/capsule sidecar.

ARQ handles deviation as suppress, observe, quarantine, review, or promotion
candidate under explicit boundary and witness discipline. This sidecar never
promotes memory directly and never writes outside a caller-provided root.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


class ArqProfileId(str, Enum):
    MEM = "ARQ-MEM"
    PLANNER = "ARQ-PLANNER"
    RAG = "ARQ-RAG"
    VISION = "ARQ-VISION"


class DetectorLayer(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class BoundaryStatus(str, Enum):
    DECLARED = "declared"
    MISSING = "missing"
    INVALID = "invalid"


class DeviationClass(str, Enum):
    DESTRUCTIVE = "destructive"
    EXPLORATORY = "exploratory"
    NEUTRAL = "neutral"
    QUARANTINED = "quarantined"


class Recommendation(str, Enum):
    SUPPRESS = "suppress"
    OBSERVE = "observe"
    CANDIDATE = "candidate"
    LOG_ONLY = "log_only"
    FAIL_CLOSED = "fail_closed"


class ArqStage(str, Enum):
    DETECTED = "detected"
    CLASSIFIED = "classified"
    SUPPRESSED = "suppressed"
    OBSERVED = "observed"
    LOG_ONLY = "log_only"
    CANDIDATE_ARTIFACT = "candidate_artifact"
    PROVISIONAL_ARTIFACT = "provisional_artifact"
    CONFIRMED_EA = "confirmed_EA"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"
    FAIL_CLOSED = "fail_closed"


class ArqEventType(str, Enum):
    DETECTED = "arq.detected"
    CLASSIFIED = "arq.classified"
    SUPPRESSION_ATTEMPTED = "arq.suppression_attempted"
    SUPPRESSION_RESULT = "arq.suppression_result"
    OBSERVE_WINDOW_OPENED = "arq.observe_window_opened"
    CANDIDATE_CREATED = "arq.candidate_created"
    PROMOTION_REQUESTED = "arq.promotion_requested"
    PROMOTION_APPROVED = "arq.promotion_approved"
    PROMOTION_DENIED = "arq.promotion_denied"
    EA_CONFIRMED = "arq.ea_confirmed"
    REJECTED = "arq.rejected"
    QUARANTINED = "arq.quarantined"
    FAIL_CLOSED = "arq.fail_closed"
    EPOCH_INVALIDATED = "arq.epoch_invalidated"
    ROLLBACK_EXECUTED = "arq.rollback_executed"


class Slot(str, Enum):
    A = "A"
    B = "B"


@dataclass(frozen=True)
class ArqProfile:
    profile_id: ArqProfileId
    direct_promotion_allowed: bool = False
    boundary_required: bool = True
    witness_required_for_candidate: bool = True
    review_required_for_promotion: bool = True
    anti_echo_required: bool = True
    strict_memory_promotion: bool = False
    requires_slot_a_valid: bool = True


@dataclass(frozen=True)
class TransitionIssue:
    rule_code: str
    message: str
    severity: str = "error"
    layer: str = "arq"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_record(self)


@dataclass(frozen=True)
class ArqCapsule:
    capsule_id: str
    profile_id: ArqProfileId
    event_stage: ArqStage
    detected_by: DetectorLayer
    boundary_status: BoundaryStatus
    boundary_id: str = ""
    deviation_class: DeviationClass = DeviationClass.NEUTRAL
    recommended_action: Recommendation = Recommendation.LOG_ONLY
    value_score: float = 0.0
    anomaly_score: float = 0.0
    witness_refs: tuple[str, ...] = ()
    anti_echo_quarantine: bool = False
    trust_valid: bool = True
    budget_valid: bool = True
    slot: Slot = Slot.A
    slot_a_valid: bool = True
    payload_hash: str = ""
    reason_codes: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArqEvent:
    event_type: ArqEventType
    event_id: str
    capsule_id: str
    occurred_at: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArqDecision:
    allowed: bool
    target_stage: ArqStage
    event_type: ArqEventType
    reason_codes: tuple[str, ...] = ()
    message: str = ""
    memory_promotion: bool = False


class ArqValidationError(ValueError):
    def __init__(self, issues: list[TransitionIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{issue.rule_code}: {issue.message}" for issue in issues))


class ArqStore:
    """Explicit-root JSON/JSONL store for ARQ capsules and events."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.base_dir = self.root / "arq"
        self.capsules_dir = self.base_dir / "capsules"
        self.events_path = self.base_dir / "events.jsonl"
        self.manifest_path = self.base_dir / "manifest.json"

    def ensure_dirs(self) -> None:
        self.capsules_dir.mkdir(parents=True, exist_ok=True)
        self.write_manifest()

    def manifest(self) -> dict[str, Any]:
        return {
            "schema": "ester.arq.store.v1",
            "purpose": "profile_capsule_sidecar",
            "capsules": str(self.capsules_dir),
            "events": str(self.events_path),
            "memory_promotion_wired": False,
        }

    def write_manifest(self) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        _write_json(self.manifest_path, self.manifest())
        return self.manifest_path

    def save_capsule(self, capsule: ArqCapsule) -> Path:
        self.ensure_dirs()
        target = self.capsules_dir / f"{_safe_file_id(capsule.capsule_id)}.json"
        _write_json(target, to_record(capsule))
        return target

    def load_capsule(self, capsule_id: str) -> dict[str, Any] | None:
        path = self.capsules_dir / f"{_safe_file_id(capsule_id)}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None

    def append_event(self, event: ArqEvent) -> Path:
        self.ensure_dirs()
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(to_record(event), ensure_ascii=False, sort_keys=True) + "\n")
        return self.events_path

    def append_events(self, events: Iterable[ArqEvent]) -> Path:
        self.ensure_dirs()
        with self.events_path.open("a", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(to_record(event), ensure_ascii=False, sort_keys=True) + "\n")
        return self.events_path

    def load_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
        return rows


def default_profiles() -> dict[ArqProfileId, ArqProfile]:
    return {
        ArqProfileId.MEM: ArqProfile(
            profile_id=ArqProfileId.MEM,
            direct_promotion_allowed=False,
            strict_memory_promotion=True,
        ),
        ArqProfileId.PLANNER: ArqProfile(profile_id=ArqProfileId.PLANNER),
        ArqProfileId.RAG: ArqProfile(profile_id=ArqProfileId.RAG),
        ArqProfileId.VISION: ArqProfile(profile_id=ArqProfileId.VISION),
    }


def get_profile(profile_id: ArqProfileId) -> ArqProfile:
    return default_profiles()[profile_id]


def detect_deviation(
    *,
    profile_id: ArqProfileId,
    detected_by: DetectorLayer,
    boundary_id: str = "",
    boundary_status: BoundaryStatus | None = None,
    capsule_id: str | None = None,
    occurred_at: str | None = None,
    payload_hash: str = "",
    metadata: dict[str, Any] | None = None,
) -> tuple[ArqCapsule, ArqEvent]:
    ts = occurred_at or _now_iso()
    status = boundary_status or (BoundaryStatus.DECLARED if boundary_id else BoundaryStatus.MISSING)
    capsule = ArqCapsule(
        capsule_id=capsule_id or f"arq:{uuid4().hex}",
        profile_id=profile_id,
        event_stage=ArqStage.DETECTED,
        detected_by=detected_by,
        boundary_status=status,
        boundary_id=str(boundary_id or ""),
        payload_hash=str(payload_hash or ""),
        created_at=ts,
        updated_at=ts,
        metadata=dict(metadata or {}),
    )
    event = ArqEvent(
        event_type=ArqEventType.DETECTED,
        event_id=_event_id("detected"),
        capsule_id=capsule.capsule_id,
        occurred_at=ts,
        payload={
            "profile_id": profile_id.value,
            "detected_by": detected_by.value,
            "boundary_status": status.value,
            "boundary_id": capsule.boundary_id,
        },
    )
    return capsule, event


def classify_capsule(
    capsule: ArqCapsule,
    *,
    deviation_class: DeviationClass,
    recommended_action: Recommendation,
    value_score: float = 0.0,
    anomaly_score: float = 0.0,
    witness_refs: Iterable[str] = (),
    anti_echo_quarantine: bool = False,
    trust_valid: bool = True,
    budget_valid: bool = True,
    slot: Slot | None = None,
    slot_a_valid: bool | None = None,
    occurred_at: str | None = None,
) -> tuple[ArqCapsule, tuple[ArqEvent, ...]]:
    ts = occurred_at or _now_iso()
    stage, reasons = _classification_stage(
        capsule,
        recommended_action=recommended_action,
        anti_echo_quarantine=anti_echo_quarantine,
        trust_valid=trust_valid,
        budget_valid=budget_valid,
    )
    updated = replace(
        capsule,
        event_stage=stage,
        deviation_class=deviation_class,
        recommended_action=recommended_action,
        value_score=float(value_score),
        anomaly_score=float(anomaly_score),
        witness_refs=tuple(str(item) for item in witness_refs if str(item)),
        anti_echo_quarantine=bool(anti_echo_quarantine),
        trust_valid=bool(trust_valid),
        budget_valid=bool(budget_valid),
        slot=slot or capsule.slot,
        slot_a_valid=capsule.slot_a_valid if slot_a_valid is None else bool(slot_a_valid),
        reason_codes=tuple(reasons),
        updated_at=ts,
    )
    classified_event = ArqEvent(
        event_type=ArqEventType.CLASSIFIED,
        event_id=_event_id("classified"),
        capsule_id=updated.capsule_id,
        occurred_at=ts,
        payload={
            "deviation_class": deviation_class.value,
            "recommended_action": recommended_action.value,
            "event_stage": updated.event_stage.value,
            "reason_codes": list(updated.reason_codes),
        },
    )
    extra_event = _event_for_stage(updated, ts)
    return updated, (classified_event, extra_event) if extra_event is not None else (classified_event,)


def request_promotion(
    capsule: ArqCapsule,
    *,
    review_approved: bool = False,
    anchor_approved: bool = False,
    high_value: bool = False,
    occurred_at: str | None = None,
) -> tuple[ArqDecision, ArqEvent]:
    ts = occurred_at or _now_iso()
    decision = validate_promotion_request(
        capsule,
        review_approved=review_approved,
        anchor_approved=anchor_approved,
        high_value=high_value,
    )
    event = ArqEvent(
        event_type=decision.event_type,
        event_id=_event_id("promotion"),
        capsule_id=capsule.capsule_id,
        occurred_at=ts,
        payload={
            "allowed": decision.allowed,
            "target_stage": decision.target_stage.value,
            "reason_codes": list(decision.reason_codes),
            "memory_promotion": decision.memory_promotion,
        },
    )
    return decision, event


def validate_promotion_request(
    capsule: ArqCapsule,
    *,
    review_approved: bool = False,
    anchor_approved: bool = False,
    high_value: bool = False,
) -> ArqDecision:
    profile = get_profile(capsule.profile_id)
    reasons: list[str] = []
    if profile.boundary_required and capsule.boundary_status != BoundaryStatus.DECLARED:
        reasons.append("ARQ_BOUNDARY_REQUIRED")
    if profile.requires_slot_a_valid and capsule.slot == Slot.B and not capsule.slot_a_valid:
        reasons.append("ARQ_SLOT_A_FAILURE")
    if capsule.anti_echo_quarantine:
        reasons.append("ARQ_ANTI_ECHO_QUARANTINE")
    if not capsule.trust_valid:
        reasons.append("ARQ_TRUST_INVALID")
    if not capsule.budget_valid:
        reasons.append("ARQ_BUDGET_INVALID")
    if profile.witness_required_for_candidate and not capsule.witness_refs:
        reasons.append("ARQ_WITNESS_REQUIRED")
    if profile.review_required_for_promotion and not review_approved:
        reasons.append("ARQ_REVIEW_REQUIRED")
    if high_value and not anchor_approved:
        reasons.append("ARQ_ANCHOR_APPROVAL_REQUIRED")
    if profile.strict_memory_promotion and not review_approved:
        reasons.append("ARQ_MEM_DIRECT_PROMOTION_DENIED")
    if capsule.event_stage not in {
        ArqStage.CANDIDATE_ARTIFACT,
        ArqStage.PROVISIONAL_ARTIFACT,
        ArqStage.OBSERVED,
    }:
        reasons.append("ARQ_STAGE_NOT_PROMOTION_ELIGIBLE")
    if reasons:
        target = ArqStage.QUARANTINED if "ARQ_ANTI_ECHO_QUARANTINE" in reasons else ArqStage.LOG_ONLY
        if "ARQ_TRUST_INVALID" in reasons or "ARQ_BUDGET_INVALID" in reasons:
            target = ArqStage.FAIL_CLOSED
        return ArqDecision(
            allowed=False,
            target_stage=target,
            event_type=ArqEventType.PROMOTION_DENIED,
            reason_codes=tuple(dict.fromkeys(reasons)),
            message="promotion denied by ARQ sidecar gates",
            memory_promotion=False,
        )
    return ArqDecision(
        allowed=True,
        target_stage=ArqStage.PROVISIONAL_ARTIFACT,
        event_type=ArqEventType.PROMOTION_APPROVED,
        reason_codes=("ARQ_PROMOTION_REVIEW_APPROVED",),
        message="promotion may proceed to provisional artifact only",
        memory_promotion=False,
    )


def to_record(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: to_record(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): to_record(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_record(item) for item in value]
    return value


def _classification_stage(
    capsule: ArqCapsule,
    *,
    recommended_action: Recommendation,
    anti_echo_quarantine: bool,
    trust_valid: bool,
    budget_valid: bool,
) -> tuple[ArqStage, list[str]]:
    reasons: list[str] = []
    if not trust_valid:
        return ArqStage.FAIL_CLOSED, ["ARQ_TRUST_INVALID"]
    if not budget_valid:
        return ArqStage.FAIL_CLOSED, ["ARQ_BUDGET_INVALID"]
    if capsule.boundary_status != BoundaryStatus.DECLARED:
        reasons.append("ARQ_BOUNDARY_REQUIRED")
        return ArqStage.LOG_ONLY, reasons
    if anti_echo_quarantine:
        reasons.append("ARQ_ANTI_ECHO_QUARANTINE")
        return ArqStage.QUARANTINED, reasons
    if recommended_action == Recommendation.SUPPRESS:
        return ArqStage.SUPPRESSED, reasons
    if recommended_action == Recommendation.OBSERVE:
        return ArqStage.OBSERVED, reasons
    if recommended_action == Recommendation.CANDIDATE:
        return ArqStage.CANDIDATE_ARTIFACT, reasons
    if recommended_action == Recommendation.FAIL_CLOSED:
        return ArqStage.FAIL_CLOSED, ["ARQ_RECOMMENDED_FAIL_CLOSED"]
    return ArqStage.LOG_ONLY, reasons


def _event_for_stage(capsule: ArqCapsule, occurred_at: str) -> ArqEvent | None:
    mapping = {
        ArqStage.SUPPRESSED: ArqEventType.SUPPRESSION_RESULT,
        ArqStage.OBSERVED: ArqEventType.OBSERVE_WINDOW_OPENED,
        ArqStage.CANDIDATE_ARTIFACT: ArqEventType.CANDIDATE_CREATED,
        ArqStage.QUARANTINED: ArqEventType.QUARANTINED,
        ArqStage.FAIL_CLOSED: ArqEventType.FAIL_CLOSED,
        ArqStage.REJECTED: ArqEventType.REJECTED,
    }
    event_type = mapping.get(capsule.event_stage)
    if event_type is None:
        return None
    return ArqEvent(
        event_type=event_type,
        event_id=_event_id(capsule.event_stage.value),
        capsule_id=capsule.capsule_id,
        occurred_at=occurred_at,
        payload={"event_stage": capsule.event_stage.value, "reason_codes": list(capsule.reason_codes)},
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _event_id(prefix: str) -> str:
    return f"arq-{prefix}:{uuid4().hex}"


def _safe_file_id(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in ("-", "_", "."):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("._") or "capsule"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
