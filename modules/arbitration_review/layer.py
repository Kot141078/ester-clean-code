"""ARL Stage 1/2 sidecar: stop and persist.

This module implements the first safe Arbitration Review Layer slice:

- open a dispute as a real hold signal
- preserve a durable dispute record
- emit minimal canonical ARL events

It is intentionally not wired into executors, volition, or hold-fire yet.
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


class ConflictClass(str, Enum):
    RUNTIME_COLLISION = "runtime_collision"
    PRIVILEGE_CONFLICT = "privilege_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    SOURCE_GROUNDING = "source_grounding"
    ORACLE_BOUNDARY = "oracle_boundary"
    UNKNOWN = "unknown"


class DisputeState(str, Enum):
    NORMAL = "NORMAL"
    PRE_ADMISSIBILITY_HOLD = "PRE_ADMISSIBILITY_HOLD"
    EVIDENTIARY_FREEZE = "EVIDENTIARY_FREEZE"
    PRIVILEGE_FREEZE = "PRIVILEGE_FREEZE"
    QUARANTINE = "QUARANTINE"
    REVIEW_ACTIVE = "REVIEW_ACTIVE"
    DELAYED_REENTRY = "DELAYED_REENTRY"
    RESOLVED = "RESOLVED"
    DEADLOCKED = "DEADLOCKED"
    IRREVERSIBLE_LOSS_ACKNOWLEDGED = "IRREVERSIBLE_LOSS_ACKNOWLEDGED"


class StandingStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class EvidencePoolStatus(str, Enum):
    PENDING = "pending"
    HELD = "held"
    FROZEN = "frozen"
    ADMITTED = "admitted"
    REJECTED = "rejected"


class ReviewMode(str, Enum):
    NONE = "none"
    MANUAL = "manual"
    TEMPLATE = "template"
    ORACLE_BOUNDED = "oracle_bounded"


class OutcomeCode(str, Enum):
    PENDING = "pending"
    UPHELD = "upheld"
    REJECTED = "rejected"
    REMEDIATED = "remediated"
    DEADLOCKED = "deadlocked"
    IRREVERSIBLE_LOSS = "irreversible_loss"


class AuthorityEffect(str, Enum):
    NONE = "none"
    HOLD = "hold"
    FREEZE = "freeze"
    QUARANTINE = "quarantine"
    RESTORE_LIMITED = "restore_limited"
    RESTORE = "restore"


class ReentryStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    DELAYED = "delayed"
    APPROVED = "approved"
    DENIED = "denied"


class ArlEventType(str, Enum):
    DISPUTE_OPENED = "arl.dispute_opened"
    STANDING_DECIDED = "arl.standing_decided"
    EVIDENCE_DECIDED = "arl.evidence_decided"
    STATE_CHANGED = "arl.state_changed"
    REVIEW_ROUTED = "arl.review_routed"
    ORACLE_REVIEW_DECIDED = "arl.oracle_review_decided"
    OUTCOME_ISSUED = "arl.outcome_issued"
    APPEAL_DECIDED = "arl.appeal_decided"
    REENTRY_DECIDED = "arl.reentry_decided"


@dataclass(frozen=True)
class ScopeRef:
    scope_id: str
    scope_kind: str
    lane: str = "runtime"


@dataclass(frozen=True)
class TransitionIssue:
    rule_code: str
    message: str
    severity: str = "error"
    layer: str = "arl"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_record(self)


@dataclass(frozen=True)
class ArlEvent:
    event_type: ArlEventType
    event_id: str
    dispute_id: str
    occurred_at: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArlDisputeRecord:
    dispute_id: str
    created_ts: str
    updated_ts: str
    conflict_class: ConflictClass
    scope_ref: ScopeRef
    state_current: DisputeState
    state_prev: DisputeState
    state_changed_ts: str
    state_reason_code: str
    standing_status: StandingStatus = StandingStatus.PENDING
    standing_class: str = ""
    standing_reason_code: str = ""
    evidence_pool_status: EvidencePoolStatus = EvidencePoolStatus.HELD
    admitted_evidence_ids: tuple[str, ...] = ()
    rejected_evidence_ids: tuple[str, ...] = ()
    review_open: bool = False
    review_mode: ReviewMode = ReviewMode.NONE
    plan_id: str = ""
    template_id: str = ""
    queue_ref: str = ""
    needs_oracle: bool = False
    oracle_request_ids: tuple[str, ...] = ()
    outcome_code: OutcomeCode = OutcomeCode.PENDING
    outcome_ts: str = ""
    authority_effect: AuthorityEffect = AuthorityEffect.HOLD
    reentry_status: ReentryStatus = ReentryStatus.NOT_REQUESTED
    reentry_window_ref: str = ""
    irreversible_flag: bool = False
    appeal_open: bool = False
    appeal_id: str = ""
    appeal_status: str = ""
    appeal_deadline_ts: str = ""
    appeal_new_basis_required: bool = True
    scar_recorded: bool = False
    scar_ref: str = ""
    precedent_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ArlValidationError(ValueError):
    def __init__(self, issues: list[TransitionIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{issue.rule_code}: {issue.message}" for issue in issues))


class ArlStore:
    """Explicit-root durable store for ARL dispute records and events."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.base_dir = self.root / "arl"
        self.disputes_dir = self.base_dir / "disputes"
        self.events_path = self.base_dir / "events.jsonl"
        self.manifest_path = self.base_dir / "manifest.json"

    def ensure_dirs(self) -> None:
        self.disputes_dir.mkdir(parents=True, exist_ok=True)
        self.write_manifest()

    def manifest(self) -> dict[str, Any]:
        return {
            "schema": "ester.arl.store.v1",
            "purpose": "stop_persist_sidecar",
            "disputes": str(self.disputes_dir),
            "events": str(self.events_path),
            "runtime_control_wired": False,
        }

    def write_manifest(self) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        _write_json(self.manifest_path, self.manifest())
        return self.manifest_path

    def save_dispute(self, record: ArlDisputeRecord) -> Path:
        _raise_if_invalid(validate_dispute_record(record))
        self.ensure_dirs()
        target = self.disputes_dir / f"{_safe_file_id(record.dispute_id)}.json"
        _write_json(target, to_record(record))
        return target

    def load_dispute(self, dispute_id: str) -> dict[str, Any] | None:
        path = self.disputes_dir / f"{_safe_file_id(dispute_id)}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None

    def append_event(self, event: ArlEvent) -> Path:
        self.ensure_dirs()
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(to_record(event), ensure_ascii=False, sort_keys=True) + "\n")
        return self.events_path

    def append_events(self, events: Iterable[ArlEvent]) -> Path:
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


def open_dispute(
    *,
    conflict_class: ConflictClass,
    scope_ref: ScopeRef,
    reason_code: str,
    dispute_id: str | None = None,
    occurred_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[ArlDisputeRecord, tuple[ArlEvent, ...]]:
    ts = occurred_at or _now_iso()
    did = dispute_id or f"dispute:{uuid4().hex}"
    record = ArlDisputeRecord(
        dispute_id=did,
        created_ts=ts,
        updated_ts=ts,
        conflict_class=conflict_class,
        scope_ref=scope_ref,
        state_current=DisputeState.PRE_ADMISSIBILITY_HOLD,
        state_prev=DisputeState.NORMAL,
        state_changed_ts=ts,
        state_reason_code=reason_code,
        metadata=dict(metadata or {}),
    )
    _raise_if_invalid(validate_dispute_record(record))
    events = (
        ArlEvent(
            event_type=ArlEventType.DISPUTE_OPENED,
            event_id=_event_id("dispute-opened"),
            dispute_id=did,
            occurred_at=ts,
            payload={
                "conflict_class": conflict_class.value,
                "scope_ref": to_record(scope_ref),
                "state_current": record.state_current.value,
                "reason_code": reason_code,
            },
        ),
        ArlEvent(
            event_type=ArlEventType.STATE_CHANGED,
            event_id=_event_id("state-changed"),
            dispute_id=did,
            occurred_at=ts,
            payload={
                "state_prev": DisputeState.NORMAL.value,
                "state_current": DisputeState.PRE_ADMISSIBILITY_HOLD.value,
                "reason_code": reason_code,
            },
        ),
    )
    return record, events


def transition_state(
    record: ArlDisputeRecord,
    *,
    state: DisputeState,
    reason_code: str,
    occurred_at: str | None = None,
    authority_effect: AuthorityEffect | None = None,
) -> tuple[ArlDisputeRecord, ArlEvent]:
    issues = _transition_issues(record, state)
    _raise_if_invalid(issues)
    ts = occurred_at or _now_iso()
    updated = replace(
        record,
        updated_ts=ts,
        state_prev=record.state_current,
        state_current=state,
        state_changed_ts=ts,
        state_reason_code=reason_code,
        authority_effect=authority_effect or _authority_for_state(state, record.authority_effect),
    )
    _raise_if_invalid(validate_dispute_record(updated))
    event = ArlEvent(
        event_type=ArlEventType.STATE_CHANGED,
        event_id=_event_id("state-changed"),
        dispute_id=record.dispute_id,
        occurred_at=ts,
        payload={
            "state_prev": record.state_current.value,
            "state_current": state.value,
            "reason_code": reason_code,
        },
    )
    return updated, event


def decide_standing(
    record: ArlDisputeRecord,
    *,
    standing_status: StandingStatus,
    standing_class: str,
    reason_code: str,
    occurred_at: str | None = None,
) -> tuple[ArlDisputeRecord, ArlEvent]:
    ts = occurred_at or _now_iso()
    updated = replace(
        record,
        updated_ts=ts,
        standing_status=standing_status,
        standing_class=standing_class,
        standing_reason_code=reason_code,
    )
    _raise_if_invalid(validate_dispute_record(updated))
    event = ArlEvent(
        event_type=ArlEventType.STANDING_DECIDED,
        event_id=_event_id("standing-decided"),
        dispute_id=record.dispute_id,
        occurred_at=ts,
        payload={
            "standing_status": standing_status.value,
            "standing_class": standing_class,
            "reason_code": reason_code,
        },
    )
    return updated, event


def decide_evidence(
    record: ArlDisputeRecord,
    *,
    evidence_pool_status: EvidencePoolStatus,
    admitted_evidence_ids: Iterable[str] = (),
    rejected_evidence_ids: Iterable[str] = (),
    reason_code: str,
    occurred_at: str | None = None,
) -> tuple[ArlDisputeRecord, ArlEvent]:
    ts = occurred_at or _now_iso()
    updated = replace(
        record,
        updated_ts=ts,
        evidence_pool_status=evidence_pool_status,
        admitted_evidence_ids=tuple(str(item) for item in admitted_evidence_ids if str(item)),
        rejected_evidence_ids=tuple(str(item) for item in rejected_evidence_ids if str(item)),
    )
    _raise_if_invalid(validate_dispute_record(updated))
    event = ArlEvent(
        event_type=ArlEventType.EVIDENCE_DECIDED,
        event_id=_event_id("evidence-decided"),
        dispute_id=record.dispute_id,
        occurred_at=ts,
        payload={
            "evidence_pool_status": evidence_pool_status.value,
            "admitted_evidence_ids": list(updated.admitted_evidence_ids),
            "rejected_evidence_ids": list(updated.rejected_evidence_ids),
            "reason_code": reason_code,
        },
    )
    return updated, event


def route_review(
    record: ArlDisputeRecord,
    *,
    review_mode: ReviewMode,
    reason_code: str,
    plan_id: str = "",
    template_id: str = "",
    queue_ref: str = "",
    needs_oracle: bool = False,
    oracle_request_ids: Iterable[str] = (),
    occurred_at: str | None = None,
) -> tuple[ArlDisputeRecord, tuple[ArlEvent, ...]]:
    issues = _routing_issues(
        record,
        review_mode=review_mode,
        template_id=template_id,
        needs_oracle=needs_oracle,
    )
    _raise_if_invalid(issues)
    ts = occurred_at or _now_iso()
    next_state = DisputeState.REVIEW_ACTIVE
    updated = replace(
        record,
        updated_ts=ts,
        state_prev=record.state_current,
        state_current=next_state,
        state_changed_ts=ts,
        state_reason_code=reason_code,
        review_open=True,
        review_mode=review_mode,
        plan_id=str(plan_id or ""),
        template_id=str(template_id or ""),
        queue_ref=str(queue_ref or ""),
        needs_oracle=bool(needs_oracle),
        oracle_request_ids=tuple(str(item) for item in oracle_request_ids if str(item)),
        authority_effect=_authority_for_state(next_state, record.authority_effect),
    )
    _raise_if_invalid(validate_dispute_record(updated))
    routed_event = ArlEvent(
        event_type=ArlEventType.REVIEW_ROUTED,
        event_id=_event_id("review-routed"),
        dispute_id=record.dispute_id,
        occurred_at=ts,
        payload={
            "review_mode": review_mode.value,
            "plan_id": updated.plan_id,
            "template_id": updated.template_id,
            "queue_ref": updated.queue_ref,
            "needs_oracle": updated.needs_oracle,
            "oracle_request_ids": list(updated.oracle_request_ids),
            "reason_code": reason_code,
        },
    )
    state_event = ArlEvent(
        event_type=ArlEventType.STATE_CHANGED,
        event_id=_event_id("state-changed"),
        dispute_id=record.dispute_id,
        occurred_at=ts,
        payload={
            "state_prev": record.state_current.value,
            "state_current": next_state.value,
            "reason_code": reason_code,
        },
    )
    return updated, (routed_event, state_event)


def validate_dispute_record(record: ArlDisputeRecord) -> list[TransitionIssue]:
    issues: list[TransitionIssue] = []
    if not str(record.dispute_id or "").strip():
        issues.append(TransitionIssue("ARL_DISPUTE_ID_REQUIRED", "dispute_id is required."))
    if not str(record.state_reason_code or "").strip():
        issues.append(TransitionIssue("ARL_REASON_REQUIRED", "state_reason_code is required."))
    if record.state_current == DisputeState.NORMAL and record.authority_effect != AuthorityEffect.NONE:
        issues.append(
            TransitionIssue(
                "ARL_NORMAL_AUTHORITY_EFFECT",
                "NORMAL state cannot carry hold/freeze/quarantine authority effect.",
            )
        )
    if record.state_current == DisputeState.EVIDENTIARY_FREEZE and record.evidence_pool_status not in {
        EvidencePoolStatus.HELD,
        EvidencePoolStatus.FROZEN,
    }:
        issues.append(
            TransitionIssue(
                "ARL_EVIDENTIARY_FREEZE_POOL",
                "EVIDENTIARY_FREEZE requires held or frozen evidence pool status.",
            )
        )
    if record.irreversible_flag and record.state_current != DisputeState.IRREVERSIBLE_LOSS_ACKNOWLEDGED:
        issues.append(
            TransitionIssue(
                "ARL_IRREVERSIBLE_STATE_REQUIRED",
                "irreversible_flag requires IRREVERSIBLE_LOSS_ACKNOWLEDGED state.",
            )
        )
    return issues


def _routing_issues(
    record: ArlDisputeRecord,
    *,
    review_mode: ReviewMode,
    template_id: str,
    needs_oracle: bool,
) -> list[TransitionIssue]:
    issues: list[TransitionIssue] = []
    if record.standing_status == StandingStatus.REJECTED:
        issues.append(
            TransitionIssue(
                "ARL_ROUTE_STANDING_REJECTED",
                "Rejected standing cannot be routed to active review.",
            )
        )
    if record.state_current in {
        DisputeState.RESOLVED,
        DisputeState.DEADLOCKED,
        DisputeState.IRREVERSIBLE_LOSS_ACKNOWLEDGED,
    }:
        issues.append(
            TransitionIssue(
                "ARL_ROUTE_TERMINAL_STATE",
                "Terminal or memory-bearing ARL states cannot be routed to active review.",
                details={"state_current": record.state_current.value},
            )
        )
    if review_mode == ReviewMode.NONE:
        issues.append(
            TransitionIssue(
                "ARL_ROUTE_MODE_REQUIRED",
                "Review routing requires a concrete review mode.",
            )
        )
    if review_mode == ReviewMode.TEMPLATE and not str(template_id or "").strip():
        issues.append(
            TransitionIssue(
                "ARL_ROUTE_TEMPLATE_REQUIRED",
                "Template review routing requires template_id.",
            )
        )
    if review_mode == ReviewMode.ORACLE_BOUNDED and not needs_oracle:
        issues.append(
            TransitionIssue(
                "ARL_ROUTE_ORACLE_FLAG_REQUIRED",
                "Oracle-bounded review routing must mark needs_oracle.",
            )
        )
    return issues


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


def _transition_issues(record: ArlDisputeRecord, target: DisputeState) -> list[TransitionIssue]:
    if record.state_current in {
        DisputeState.RESOLVED,
        DisputeState.DEADLOCKED,
        DisputeState.IRREVERSIBLE_LOSS_ACKNOWLEDGED,
    } and target == DisputeState.NORMAL:
        return [
            TransitionIssue(
                "ARL_REENTRY_DECISION_REQUIRED",
                "Terminal or memory-bearing ARL states cannot silently re-enter NORMAL.",
                details={"state_current": record.state_current.value, "target": target.value},
            )
        ]
    return []


def _authority_for_state(state: DisputeState, current: AuthorityEffect) -> AuthorityEffect:
    if state == DisputeState.NORMAL:
        return AuthorityEffect.NONE
    if state in {DisputeState.EVIDENTIARY_FREEZE, DisputeState.PRIVILEGE_FREEZE}:
        return AuthorityEffect.FREEZE
    if state == DisputeState.QUARANTINE:
        return AuthorityEffect.QUARANTINE
    if state == DisputeState.RESOLVED:
        return AuthorityEffect.RESTORE_LIMITED
    return current if current != AuthorityEffect.NONE else AuthorityEffect.HOLD


def _raise_if_invalid(issues: list[TransitionIssue]) -> None:
    if issues:
        raise ArlValidationError(issues)


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


def _event_id(prefix: str) -> str:
    return f"{prefix}:{uuid4().hex}"


def _safe_file_id(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in ("-", "_", "."):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("._") or "dispute"
