"""Actor Grounding Layer sidecar.

AGL qualifies a source before runtime reliance. This implementation is a
sidecar only: it computes and persists bounded decisions without wiring them
into executor, ARL, or commit authority.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class SourceClass(str, Enum):
    HUMAN_OPERATOR = "human_operator"
    LOCAL_ENTITY = "local_entity"
    SENSOR_PERCEPTION = "sensor_perception"
    DELEGATED_PROXY_EXTERNAL = "delegated_proxy_external"
    UNKNOWN = "unknown"


class GroundingState(str, Enum):
    GROUNDED = "GROUNDED"
    GROUNDED_WITH_CAUTION = "GROUNDED_WITH_CAUTION"
    HOLD_REQUIRED = "HOLD_REQUIRED"
    RUNTIME_RELIANCE_DENIED = "RUNTIME_RELIANCE_DENIED"
    QUARANTINE_REQUIRED = "QUARANTINE_REQUIRED"
    REVALIDATE_AT_COMMIT = "REVALIDATE_AT_COMMIT"


class RuntimeReliance(str, Enum):
    RECORD_ONLY = "RECORD_ONLY"
    VISIBLE_BUT_NON_AUTHORITATIVE = "VISIBLE_BUT_NON_AUTHORITATIVE"
    REVIEW_SUPPORT_ONLY = "REVIEW_SUPPORT_ONLY"
    ESCALATION_ELIGIBLE = "ESCALATION_ELIGIBLE"
    ACTION_ELIGIBLE_WITH_LIMITS = "ACTION_ELIGIBLE_WITH_LIMITS"
    COMMIT_ELIGIBLE = "COMMIT_ELIGIBLE"
    RUNTIME_RELIANCE_DENIED = "RUNTIME_RELIANCE_DENIED"


class GateOutcome(str, Enum):
    OPEN = "OPEN"
    OPEN_WITH_LIMITS = "OPEN_WITH_LIMITS"
    HOLD = "HOLD"
    REROUTE_TO_REVIEW = "REROUTE_TO_REVIEW"
    DENY = "DENY"
    QUARANTINE = "QUARANTINE"
    REVALIDATE_AT_COMMIT = "REVALIDATE_AT_COMMIT"


class DegradationLevel(str, Enum):
    NO_MATERIAL_DEGRADATION = "NO_MATERIAL_DEGRADATION"
    CAUTIONARY_DEGRADATION = "CAUTIONARY_DEGRADATION"
    HOLD_TRIGGERING_DEGRADATION = "HOLD_TRIGGERING_DEGRADATION"
    FREEZE_TRIGGERING_DEGRADATION = "FREEZE_TRIGGERING_DEGRADATION"
    QUARANTINE_TRIGGERING_DEGRADATION = "QUARANTINE_TRIGGERING_DEGRADATION"
    COMMIT_BLOCKING_DEGRADATION = "COMMIT_BLOCKING_DEGRADATION"


@dataclass(frozen=True)
class ActorSourceState:
    source_id: str
    source_class: SourceClass
    observed_at: str
    present_at_boundary: bool = True
    identity_continuity: bool = True
    authority_continuity: bool = True
    perceptual_integrity: bool = True
    freshness_sec: int = 0
    max_freshness_sec: int = 300
    proxy_depth: int = 0
    degradation: DegradationLevel = DegradationLevel.NO_MATERIAL_DEGRADATION
    requires_commit_revalidation: bool = False
    evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransitionIssue:
    rule_code: str
    message: str
    severity: str = "error"
    layer: str = "agl"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_record(self)


@dataclass(frozen=True)
class ActorGroundingDecision:
    decision_id: str
    created_at: str
    source_id: str
    source_class: SourceClass
    grounding_state: GroundingState
    runtime_reliance: RuntimeReliance
    gate_outcome: GateOutcome
    degradation: DegradationLevel
    requested_reliance: RuntimeReliance
    revalidate_at_commit: bool = False
    reason_codes: tuple[str, ...] = ()
    limits: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)


class AglValidationError(ValueError):
    def __init__(self, issues: list[TransitionIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{issue.rule_code}: {issue.message}" for issue in issues))


class ActorGroundingStore:
    """Explicit-root JSONL store for AGL source-state decisions."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.base_dir = self.root / "actor_grounding"
        self.decisions_path = self.base_dir / "decisions.jsonl"
        self.manifest_path = self.base_dir / "manifest.json"

    def ensure_dirs(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.write_manifest()

    def manifest(self) -> dict[str, Any]:
        return {
            "schema": "ester.agl.store.v1",
            "purpose": "source_grounding_sidecar",
            "decisions": str(self.decisions_path),
            "runtime_control_wired": False,
        }

    def write_manifest(self) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        _write_json(self.manifest_path, self.manifest())
        return self.manifest_path

    def append_decision(self, decision: ActorGroundingDecision) -> Path:
        self.ensure_dirs()
        with self.decisions_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(to_record(decision), ensure_ascii=False, sort_keys=True) + "\n")
        return self.decisions_path

    def load_decisions(self) -> list[dict[str, Any]]:
        if not self.decisions_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.decisions_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
        return rows


def evaluate_source_state(
    source: ActorSourceState,
    *,
    requested_reliance: RuntimeReliance = RuntimeReliance.ACTION_ELIGIBLE_WITH_LIMITS,
    decision_id: str | None = None,
    created_at: str | None = None,
) -> ActorGroundingDecision:
    reasons = _source_reason_codes(source)
    effective_degradation = _effective_degradation(source, requested_reliance, reasons)
    grounding, reliance, gate = _map_degradation(
        effective_degradation,
        requested_reliance=requested_reliance,
        requires_commit_revalidation=source.requires_commit_revalidation,
    )
    limits = _limits_for(source, grounding, gate)
    decision = ActorGroundingDecision(
        decision_id=decision_id or f"agl:{uuid4().hex}",
        created_at=created_at or _now_iso(),
        source_id=source.source_id,
        source_class=source.source_class,
        grounding_state=grounding,
        runtime_reliance=reliance,
        gate_outcome=gate,
        degradation=effective_degradation,
        requested_reliance=requested_reliance,
        revalidate_at_commit=bool(
            source.requires_commit_revalidation
            or gate == GateOutcome.REVALIDATE_AT_COMMIT
            or grounding == GroundingState.REVALIDATE_AT_COMMIT
        ),
        reason_codes=tuple(reasons),
        limits=tuple(limits),
        evidence_refs=tuple(str(item) for item in source.evidence_refs if str(item)),
        details={
            "freshness_sec": int(source.freshness_sec),
            "max_freshness_sec": int(source.max_freshness_sec),
            "proxy_depth": int(source.proxy_depth),
            "identity_continuity": bool(source.identity_continuity),
            "authority_continuity": bool(source.authority_continuity),
            "perceptual_integrity": bool(source.perceptual_integrity),
            **dict(source.metadata or {}),
        },
    )
    _raise_if_invalid(_decision_issues(decision))
    return decision


def validate_reliance_transition(
    previous: ActorGroundingDecision,
    current: ActorGroundingDecision,
    *,
    fresh_grounding_basis: bool = False,
) -> list[TransitionIssue]:
    issues: list[TransitionIssue] = []
    unresolved = previous.degradation != DegradationLevel.NO_MATERIAL_DEGRADATION
    widened = reliance_rank(current.runtime_reliance) > reliance_rank(previous.runtime_reliance)
    if unresolved and widened and not fresh_grounding_basis:
        issues.append(
            TransitionIssue(
                "AGL_UNRESOLVED_DEGRADATION_WIDENING",
                "Unresolved degradation may not widen runtime reliance without fresh grounding basis.",
                details={
                    "previous_reliance": previous.runtime_reliance.value,
                    "current_reliance": current.runtime_reliance.value,
                },
            )
        )
    if (
        current.degradation == DegradationLevel.COMMIT_BLOCKING_DEGRADATION
        and current.runtime_reliance == RuntimeReliance.COMMIT_ELIGIBLE
    ):
        issues.append(
            TransitionIssue(
                "AGL_COMMIT_BLOCKING_RELIANCE",
                "Commit-blocking degradation cannot produce COMMIT_ELIGIBLE reliance.",
            )
        )
    return issues


def reliance_rank(reliance: RuntimeReliance) -> int:
    if reliance == RuntimeReliance.RUNTIME_RELIANCE_DENIED:
        return -1
    order = {
        RuntimeReliance.RECORD_ONLY: 0,
        RuntimeReliance.VISIBLE_BUT_NON_AUTHORITATIVE: 1,
        RuntimeReliance.REVIEW_SUPPORT_ONLY: 2,
        RuntimeReliance.ESCALATION_ELIGIBLE: 3,
        RuntimeReliance.ACTION_ELIGIBLE_WITH_LIMITS: 4,
        RuntimeReliance.COMMIT_ELIGIBLE: 5,
    }
    return order[reliance]


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


def _source_reason_codes(source: ActorSourceState) -> list[str]:
    reasons: list[str] = []
    if not str(source.source_id or "").strip():
        reasons.append("SOURCE_ID_REQUIRED")
    if not source.present_at_boundary:
        reasons.append("SOURCE_NOT_PRESENT_AT_BOUNDARY")
    if not source.identity_continuity:
        reasons.append("IDENTITY_CONTINUITY_BROKEN")
    if not source.authority_continuity:
        reasons.append("AUTHORITY_CONTINUITY_BROKEN")
    if not source.perceptual_integrity:
        reasons.append("PERCEPTUAL_INTEGRITY_BROKEN")
    if int(source.max_freshness_sec) >= 0 and int(source.freshness_sec) > int(source.max_freshness_sec):
        reasons.append("SOURCE_STALE_AT_BOUNDARY")
    if source.source_class == SourceClass.DELEGATED_PROXY_EXTERNAL and int(source.proxy_depth) >= 3:
        reasons.append("PROXY_TOO_ABSTRACTED")
    return reasons


def _effective_degradation(
    source: ActorSourceState,
    requested_reliance: RuntimeReliance,
    reasons: list[str],
) -> DegradationLevel:
    degradation = source.degradation
    if "SOURCE_ID_REQUIRED" in reasons or "SOURCE_NOT_PRESENT_AT_BOUNDARY" in reasons:
        return DegradationLevel.QUARANTINE_TRIGGERING_DEGRADATION
    if "IDENTITY_CONTINUITY_BROKEN" in reasons or "AUTHORITY_CONTINUITY_BROKEN" in reasons:
        return _max_degradation(degradation, DegradationLevel.FREEZE_TRIGGERING_DEGRADATION)
    if "PERCEPTUAL_INTEGRITY_BROKEN" in reasons:
        return _max_degradation(degradation, DegradationLevel.HOLD_TRIGGERING_DEGRADATION)
    if "PROXY_TOO_ABSTRACTED" in reasons:
        return _max_degradation(degradation, DegradationLevel.HOLD_TRIGGERING_DEGRADATION)
    if "SOURCE_STALE_AT_BOUNDARY" in reasons:
        if requested_reliance == RuntimeReliance.COMMIT_ELIGIBLE:
            return _max_degradation(degradation, DegradationLevel.COMMIT_BLOCKING_DEGRADATION)
        return _max_degradation(degradation, DegradationLevel.HOLD_TRIGGERING_DEGRADATION)
    return degradation


def _map_degradation(
    degradation: DegradationLevel,
    *,
    requested_reliance: RuntimeReliance,
    requires_commit_revalidation: bool,
) -> tuple[GroundingState, RuntimeReliance, GateOutcome]:
    if degradation == DegradationLevel.NO_MATERIAL_DEGRADATION:
        if requires_commit_revalidation:
            return (
                GroundingState.REVALIDATE_AT_COMMIT,
                _min_reliance(requested_reliance, RuntimeReliance.ACTION_ELIGIBLE_WITH_LIMITS),
                GateOutcome.REVALIDATE_AT_COMMIT,
            )
        return GroundingState.GROUNDED, requested_reliance, GateOutcome.OPEN
    if degradation == DegradationLevel.CAUTIONARY_DEGRADATION:
        return (
            GroundingState.GROUNDED_WITH_CAUTION,
            _min_reliance(requested_reliance, RuntimeReliance.ACTION_ELIGIBLE_WITH_LIMITS),
            GateOutcome.OPEN_WITH_LIMITS,
        )
    if degradation == DegradationLevel.HOLD_TRIGGERING_DEGRADATION:
        return (
            GroundingState.HOLD_REQUIRED,
            RuntimeReliance.REVIEW_SUPPORT_ONLY,
            GateOutcome.HOLD,
        )
    if degradation == DegradationLevel.FREEZE_TRIGGERING_DEGRADATION:
        return (
            GroundingState.HOLD_REQUIRED,
            RuntimeReliance.REVIEW_SUPPORT_ONLY,
            GateOutcome.REROUTE_TO_REVIEW,
        )
    if degradation == DegradationLevel.QUARANTINE_TRIGGERING_DEGRADATION:
        return (
            GroundingState.QUARANTINE_REQUIRED,
            RuntimeReliance.RUNTIME_RELIANCE_DENIED,
            GateOutcome.QUARANTINE,
        )
    if degradation == DegradationLevel.COMMIT_BLOCKING_DEGRADATION:
        return (
            GroundingState.REVALIDATE_AT_COMMIT,
            RuntimeReliance.REVIEW_SUPPORT_ONLY,
            GateOutcome.DENY
            if requested_reliance == RuntimeReliance.COMMIT_ELIGIBLE
            else GateOutcome.REVALIDATE_AT_COMMIT,
        )
    return (
        GroundingState.RUNTIME_RELIANCE_DENIED,
        RuntimeReliance.RUNTIME_RELIANCE_DENIED,
        GateOutcome.DENY,
    )


def _limits_for(
    source: ActorSourceState,
    grounding: GroundingState,
    gate: GateOutcome,
) -> list[str]:
    limits: list[str] = []
    if grounding == GroundingState.GROUNDED_WITH_CAUTION:
        limits.extend(["narrow_privilege", "stronger_logging", "shorter_window"])
    if grounding in {GroundingState.HOLD_REQUIRED, GroundingState.REVALIDATE_AT_COMMIT}:
        limits.append("fresh_grounding_required")
    if gate == GateOutcome.REROUTE_TO_REVIEW:
        limits.append("review_route_required")
    if gate == GateOutcome.QUARANTINE:
        limits.append("isolate_source_path")
    if source.source_class == SourceClass.HUMAN_OPERATOR and source.degradation != DegradationLevel.NO_MATERIAL_DEGRADATION:
        limits.append("preserve_agency_without_full_runtime_force")
    return limits


def _decision_issues(decision: ActorGroundingDecision) -> list[TransitionIssue]:
    issues: list[TransitionIssue] = []
    if not str(decision.source_id or "").strip():
        issues.append(TransitionIssue("AGL_SOURCE_ID_REQUIRED", "source_id is required."))
    if (
        decision.degradation == DegradationLevel.COMMIT_BLOCKING_DEGRADATION
        and decision.runtime_reliance == RuntimeReliance.COMMIT_ELIGIBLE
    ):
        issues.append(
            TransitionIssue(
                "AGL_COMMIT_BLOCKING_RELIANCE",
                "Commit-blocking degradation cannot produce COMMIT_ELIGIBLE reliance.",
            )
        )
    if (
        decision.gate_outcome == GateOutcome.QUARANTINE
        and decision.grounding_state != GroundingState.QUARANTINE_REQUIRED
    ):
        issues.append(
            TransitionIssue(
                "AGL_QUARANTINE_STATE_REQUIRED",
                "QUARANTINE gate requires QUARANTINE_REQUIRED grounding state.",
            )
        )
    return issues


def _min_reliance(a: RuntimeReliance, b: RuntimeReliance) -> RuntimeReliance:
    return a if reliance_rank(a) <= reliance_rank(b) else b


_DEGRADATION_ORDER = {
    DegradationLevel.NO_MATERIAL_DEGRADATION: 0,
    DegradationLevel.CAUTIONARY_DEGRADATION: 1,
    DegradationLevel.HOLD_TRIGGERING_DEGRADATION: 2,
    DegradationLevel.FREEZE_TRIGGERING_DEGRADATION: 3,
    DegradationLevel.QUARANTINE_TRIGGERING_DEGRADATION: 4,
    DegradationLevel.COMMIT_BLOCKING_DEGRADATION: 5,
}


def _max_degradation(a: DegradationLevel, b: DegradationLevel) -> DegradationLevel:
    return a if _DEGRADATION_ORDER[a] >= _DEGRADATION_ORDER[b] else b


def _raise_if_invalid(issues: list[TransitionIssue]) -> None:
    if issues:
        raise AglValidationError(issues)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
