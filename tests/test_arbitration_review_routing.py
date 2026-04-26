import pytest

from modules.arbitration_review import (
    ArlStore,
    ArlValidationError,
    ArlWitnessLedger,
    ConflictClass,
    DisputeState,
    EvidencePoolStatus,
    ReviewMode,
    ScopeRef,
    StandingStatus,
    decide_evidence,
    decide_standing,
    open_dispute,
    route_review,
    transition_state,
)


def _routable_dispute():
    record, events = open_dispute(
        conflict_class=ConflictClass.RUNTIME_COLLISION,
        scope_ref=ScopeRef("glitch:collision-route", "GlitchNode"),
        reason_code="runtime_collision_registered",
        dispute_id="dispute-route-1",
    )
    record, standing_event = decide_standing(
        record,
        standing_status=StandingStatus.ACCEPTED,
        standing_class="runtime_collision",
        reason_code="standing_accepted",
    )
    record, evidence_event = decide_evidence(
        record,
        evidence_pool_status=EvidencePoolStatus.FROZEN,
        admitted_evidence_ids=["evidence:collision-route"],
        reason_code="evidence_frozen",
    )
    return record, (*events, standing_event, evidence_event)


def test_route_review_opens_review_active_and_persists(tmp_path):
    record, events = _routable_dispute()

    routed, route_events = route_review(
        record,
        review_mode=ReviewMode.TEMPLATE,
        template_id="arl.runtime_collision.v1",
        queue_ref="queue:arl",
        reason_code="route_runtime_collision_review",
    )
    store = ArlStore(tmp_path)
    store.save_dispute(routed)
    store.append_events((*events, *route_events))

    loaded = store.load_dispute("dispute-route-1")
    loaded_events = store.load_events()

    assert routed.review_open is True
    assert routed.review_mode == ReviewMode.TEMPLATE
    assert routed.state_current == DisputeState.REVIEW_ACTIVE
    assert loaded["review_open"] is True
    assert loaded["review_mode"] == "template"
    assert loaded["state_current"] == "REVIEW_ACTIVE"
    assert [event["event_type"] for event in loaded_events[-2:]] == [
        "arl.review_routed",
        "arl.state_changed",
    ]


def test_route_review_event_can_receive_witness_footprint(tmp_path):
    record, _ = _routable_dispute()
    _, route_events = route_review(
        record,
        review_mode=ReviewMode.MANUAL,
        queue_ref="queue:manual-review",
        reason_code="route_manual_review",
    )
    footprints = ArlWitnessLedger(tmp_path).append_events(route_events, witness_id="witness:arl")

    assert [fp.event_type.value for fp in footprints] == ["arl.review_routed", "arl.state_changed"]
    assert ArlWitnessLedger(tmp_path).verify_chain()["ok"] is True


def test_route_review_rejects_rejected_standing():
    record, _ = open_dispute(
        conflict_class=ConflictClass.UNKNOWN,
        scope_ref=ScopeRef("scope:rejected", "unknown"),
        reason_code="opened",
        dispute_id="dispute-route-2",
    )
    record, _ = decide_standing(
        record,
        standing_status=StandingStatus.REJECTED,
        standing_class="out_of_scope",
        reason_code="standing_rejected",
    )

    with pytest.raises(ArlValidationError) as exc:
        route_review(record, review_mode=ReviewMode.MANUAL, reason_code="should_not_route")

    assert any(issue.rule_code == "ARL_ROUTE_STANDING_REJECTED" for issue in exc.value.issues)


def test_route_review_rejects_oracle_mode_without_oracle_flag():
    record, _ = _routable_dispute()

    with pytest.raises(ArlValidationError) as exc:
        route_review(
            record,
            review_mode=ReviewMode.ORACLE_BOUNDED,
            reason_code="oracle_route_without_flag",
        )

    assert any(issue.rule_code == "ARL_ROUTE_ORACLE_FLAG_REQUIRED" for issue in exc.value.issues)


def test_route_review_rejects_terminal_state():
    record, _ = _routable_dispute()
    resolved, _ = transition_state(
        record,
        state=DisputeState.RESOLVED,
        reason_code="resolved",
    )

    with pytest.raises(ArlValidationError) as exc:
        route_review(resolved, review_mode=ReviewMode.MANUAL, reason_code="late_route")

    assert any(issue.rule_code == "ARL_ROUTE_TERMINAL_STATE" for issue in exc.value.issues)
