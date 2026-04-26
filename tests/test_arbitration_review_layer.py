import pytest

from modules.arbitration_review import (
    ArlStore,
    ArlValidationError,
    ConflictClass,
    DisputeState,
    EvidencePoolStatus,
    ScopeRef,
    StandingStatus,
    decide_evidence,
    decide_standing,
    open_dispute,
    transition_state,
)


def test_open_dispute_creates_real_hold_and_events(tmp_path):
    record, events = open_dispute(
        conflict_class=ConflictClass.RUNTIME_COLLISION,
        scope_ref=ScopeRef("glitch:collision-1", "GlitchNode"),
        reason_code="runtime_collision_registered",
        dispute_id="dispute-1",
        occurred_at="2026-04-26T00:00:00+00:00",
    )

    assert record.state_prev == DisputeState.NORMAL
    assert record.state_current == DisputeState.PRE_ADMISSIBILITY_HOLD
    assert record.evidence_pool_status == EvidencePoolStatus.HELD
    assert [event.event_type.value for event in events] == [
        "arl.dispute_opened",
        "arl.state_changed",
    ]

    store = ArlStore(tmp_path)
    store.save_dispute(record)
    store.append_events(events)

    loaded = ArlStore(tmp_path).load_dispute("dispute-1")
    assert loaded["state_current"] == "PRE_ADMISSIBILITY_HOLD"
    assert loaded["scope_ref"]["scope_id"] == "glitch:collision-1"
    assert [event["event_type"] for event in ArlStore(tmp_path).load_events()] == [
        "arl.dispute_opened",
        "arl.state_changed",
    ]


def test_standing_and_evidence_decisions_are_persisted(tmp_path):
    record, events = open_dispute(
        conflict_class=ConflictClass.EVIDENCE_CONFLICT,
        scope_ref=ScopeRef("evidence:1", "EvidenceRecord"),
        reason_code="evidence_conflict",
        dispute_id="dispute-2",
    )
    record, standing_event = decide_standing(
        record,
        standing_status=StandingStatus.ACCEPTED,
        standing_class="direct_runtime_conflict",
        reason_code="scope_has_standing",
    )
    record, evidence_event = decide_evidence(
        record,
        evidence_pool_status=EvidencePoolStatus.FROZEN,
        admitted_evidence_ids=["evidence:1"],
        reason_code="freeze_admitted_evidence",
    )
    record, state_event = transition_state(
        record,
        state=DisputeState.EVIDENTIARY_FREEZE,
        reason_code="evidence_freeze",
    )

    store = ArlStore(tmp_path)
    store.save_dispute(record)
    store.append_events((*events, standing_event, evidence_event, state_event))
    loaded = store.load_dispute("dispute-2")

    assert loaded["standing_status"] == "accepted"
    assert loaded["evidence_pool_status"] == "frozen"
    assert loaded["admitted_evidence_ids"] == ["evidence:1"]
    assert loaded["state_current"] == "EVIDENTIARY_FREEZE"


def test_resolved_dispute_cannot_silently_reenter_normal():
    record, _ = open_dispute(
        conflict_class=ConflictClass.UNKNOWN,
        scope_ref=ScopeRef("scope:1", "unknown"),
        reason_code="opened",
        dispute_id="dispute-3",
    )
    record, _ = transition_state(
        record,
        state=DisputeState.RESOLVED,
        reason_code="resolved_with_limits",
    )

    with pytest.raises(ArlValidationError) as exc:
        transition_state(record, state=DisputeState.NORMAL, reason_code="silent_reentry")

    assert any(issue.rule_code == "ARL_REENTRY_DECISION_REQUIRED" for issue in exc.value.issues)


def test_arl_store_manifest_marks_no_runtime_wiring(tmp_path):
    store = ArlStore(tmp_path)
    store.ensure_dirs()

    manifest = store.manifest()

    assert manifest["schema"] == "ester.arl.store.v1"
    assert manifest["purpose"] == "stop_persist_sidecar"
    assert manifest["runtime_control_wired"] is False
