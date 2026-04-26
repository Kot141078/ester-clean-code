from modules.actor_grounding import (
    ActorGroundingStore,
    ActorSourceState,
    DegradationLevel,
    GateOutcome,
    GroundingState,
    RuntimeReliance,
    SourceClass,
    evaluate_source_state,
    validate_reliance_transition,
)


def test_grounded_source_can_be_commit_eligible_and_persisted(tmp_path):
    source = ActorSourceState(
        source_id="operator:primary",
        source_class=SourceClass.HUMAN_OPERATOR,
        observed_at="2026-04-26T00:00:00+00:00",
        evidence_refs=("witness:operator-present",),
    )

    decision = evaluate_source_state(
        source,
        requested_reliance=RuntimeReliance.COMMIT_ELIGIBLE,
        decision_id="agl-decision-1",
    )
    store = ActorGroundingStore(tmp_path)
    store.append_decision(decision)

    loaded = ActorGroundingStore(tmp_path).load_decisions()
    assert decision.grounding_state == GroundingState.GROUNDED
    assert decision.runtime_reliance == RuntimeReliance.COMMIT_ELIGIBLE
    assert decision.gate_outcome == GateOutcome.OPEN
    assert loaded[0]["source_id"] == "operator:primary"
    assert loaded[0]["runtime_reliance"] == "COMMIT_ELIGIBLE"
    assert store.manifest()["runtime_control_wired"] is False


def test_human_caution_narrows_authority_without_erasing_agency():
    source = ActorSourceState(
        source_id="operator:tired",
        source_class=SourceClass.HUMAN_OPERATOR,
        observed_at="2026-04-26T00:00:00+00:00",
        degradation=DegradationLevel.CAUTIONARY_DEGRADATION,
    )

    decision = evaluate_source_state(source, requested_reliance=RuntimeReliance.COMMIT_ELIGIBLE)

    assert decision.grounding_state == GroundingState.GROUNDED_WITH_CAUTION
    assert decision.runtime_reliance == RuntimeReliance.ACTION_ELIGIBLE_WITH_LIMITS
    assert decision.gate_outcome == GateOutcome.OPEN_WITH_LIMITS
    assert "preserve_agency_without_full_runtime_force" in decision.limits


def test_stale_sensor_enters_hold_and_review_support_only():
    source = ActorSourceState(
        source_id="sensor:camera-1",
        source_class=SourceClass.SENSOR_PERCEPTION,
        observed_at="2026-04-26T00:00:00+00:00",
        freshness_sec=900,
        max_freshness_sec=60,
    )

    decision = evaluate_source_state(source)

    assert decision.grounding_state == GroundingState.HOLD_REQUIRED
    assert decision.runtime_reliance == RuntimeReliance.REVIEW_SUPPORT_ONLY
    assert decision.gate_outcome == GateOutcome.HOLD
    assert "SOURCE_STALE_AT_BOUNDARY" in decision.reason_codes


def test_proxy_abstraction_cannot_launder_runtime_trust():
    source = ActorSourceState(
        source_id="proxy:remote",
        source_class=SourceClass.DELEGATED_PROXY_EXTERNAL,
        observed_at="2026-04-26T00:00:00+00:00",
        proxy_depth=3,
    )

    decision = evaluate_source_state(source, requested_reliance=RuntimeReliance.COMMIT_ELIGIBLE)

    assert decision.grounding_state == GroundingState.HOLD_REQUIRED
    assert decision.runtime_reliance == RuntimeReliance.REVIEW_SUPPORT_ONLY
    assert "PROXY_TOO_ABSTRACTED" in decision.reason_codes


def test_commit_blocking_degradation_denies_commit():
    source = ActorSourceState(
        source_id="operator:commit",
        source_class=SourceClass.HUMAN_OPERATOR,
        observed_at="2026-04-26T00:00:00+00:00",
        degradation=DegradationLevel.COMMIT_BLOCKING_DEGRADATION,
    )

    decision = evaluate_source_state(source, requested_reliance=RuntimeReliance.COMMIT_ELIGIBLE)

    assert decision.gate_outcome == GateOutcome.DENY
    assert decision.runtime_reliance != RuntimeReliance.COMMIT_ELIGIBLE
    assert decision.revalidate_at_commit is True


def test_quarantine_triggering_degradation_denies_runtime_reliance():
    source = ActorSourceState(
        source_id="source:detached",
        source_class=SourceClass.LOCAL_ENTITY,
        observed_at="2026-04-26T00:00:00+00:00",
        degradation=DegradationLevel.QUARANTINE_TRIGGERING_DEGRADATION,
    )

    decision = evaluate_source_state(source)

    assert decision.grounding_state == GroundingState.QUARANTINE_REQUIRED
    assert decision.runtime_reliance == RuntimeReliance.RUNTIME_RELIANCE_DENIED
    assert decision.gate_outcome == GateOutcome.QUARANTINE
    assert "isolate_source_path" in decision.limits


def test_unresolved_degradation_cannot_widen_without_fresh_basis():
    previous = evaluate_source_state(
        ActorSourceState(
            source_id="operator:limited",
            source_class=SourceClass.HUMAN_OPERATOR,
            observed_at="2026-04-26T00:00:00+00:00",
            degradation=DegradationLevel.CAUTIONARY_DEGRADATION,
        ),
        requested_reliance=RuntimeReliance.COMMIT_ELIGIBLE,
    )
    current = evaluate_source_state(
        ActorSourceState(
            source_id="operator:limited",
            source_class=SourceClass.HUMAN_OPERATOR,
            observed_at="2026-04-26T00:10:00+00:00",
        ),
        requested_reliance=RuntimeReliance.COMMIT_ELIGIBLE,
    )

    issues = validate_reliance_transition(previous, current)
    allowed_after_fresh_basis = validate_reliance_transition(
        previous,
        current,
        fresh_grounding_basis=True,
    )

    assert issues[0].rule_code == "AGL_UNRESOLVED_DEGRADATION_WIDENING"
    assert allowed_after_fresh_basis == []
