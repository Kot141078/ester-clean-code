from modules.arq import (
    ArqProfileId,
    ArqStage,
    ArqStore,
    BoundaryStatus,
    DetectorLayer,
    DeviationClass,
    Recommendation,
    Slot,
    classify_capsule,
    default_profiles,
    detect_deviation,
    request_promotion,
)


def test_arq_profiles_are_declared_and_mem_is_strict():
    profiles = default_profiles()

    assert set(profiles) == {
        ArqProfileId.MEM,
        ArqProfileId.PLANNER,
        ArqProfileId.RAG,
        ArqProfileId.VISION,
    }
    assert profiles[ArqProfileId.MEM].strict_memory_promotion is True
    assert profiles[ArqProfileId.MEM].direct_promotion_allowed is False


def test_no_boundary_allows_log_only_at_most():
    capsule, detected_event = detect_deviation(
        profile_id=ArqProfileId.MEM,
        detected_by=DetectorLayer.L2,
        capsule_id="capsule-no-boundary",
    )
    capsule, events = classify_capsule(
        capsule,
        deviation_class=DeviationClass.EXPLORATORY,
        recommended_action=Recommendation.CANDIDATE,
        witness_refs=["witness:1"],
    )
    decision, promotion_event = request_promotion(capsule, review_approved=True)

    assert detected_event.event_type.value == "arq.detected"
    assert capsule.boundary_status == BoundaryStatus.MISSING
    assert capsule.event_stage == ArqStage.LOG_ONLY
    assert "ARQ_BOUNDARY_REQUIRED" in capsule.reason_codes
    assert [event.event_type.value for event in events] == ["arq.classified"]
    assert decision.allowed is False
    assert decision.target_stage == ArqStage.LOG_ONLY
    assert promotion_event.event_type.value == "arq.promotion_denied"


def test_arq_mem_direct_promotion_is_denied_without_review():
    capsule, _ = detect_deviation(
        profile_id=ArqProfileId.MEM,
        detected_by=DetectorLayer.L2,
        boundary_id="boundary:mem",
        capsule_id="capsule-mem",
    )
    capsule, _ = classify_capsule(
        capsule,
        deviation_class=DeviationClass.EXPLORATORY,
        recommended_action=Recommendation.CANDIDATE,
        witness_refs=["witness:mem"],
    )
    decision, _ = request_promotion(capsule, review_approved=False)

    assert capsule.event_stage == ArqStage.CANDIDATE_ARTIFACT
    assert decision.allowed is False
    assert "ARQ_REVIEW_REQUIRED" in decision.reason_codes
    assert "ARQ_MEM_DIRECT_PROMOTION_DENIED" in decision.reason_codes
    assert decision.memory_promotion is False


def test_reviewed_arq_mem_reaches_only_provisional_artifact_not_memory_promotion():
    capsule, _ = detect_deviation(
        profile_id=ArqProfileId.MEM,
        detected_by=DetectorLayer.L2,
        boundary_id="boundary:mem",
        capsule_id="capsule-reviewed",
    )
    capsule, _ = classify_capsule(
        capsule,
        deviation_class=DeviationClass.EXPLORATORY,
        recommended_action=Recommendation.CANDIDATE,
        witness_refs=["witness:mem", "review:1"],
    )
    decision, event = request_promotion(capsule, review_approved=True)

    assert decision.allowed is True
    assert decision.target_stage == ArqStage.PROVISIONAL_ARTIFACT
    assert decision.memory_promotion is False
    assert event.event_type.value == "arq.promotion_approved"


def test_anti_echo_quarantine_freezes_promotion():
    capsule, _ = detect_deviation(
        profile_id=ArqProfileId.PLANNER,
        detected_by=DetectorLayer.L1,
        boundary_id="boundary:planner",
        capsule_id="capsule-echo",
    )
    capsule, events = classify_capsule(
        capsule,
        deviation_class=DeviationClass.EXPLORATORY,
        recommended_action=Recommendation.CANDIDATE,
        witness_refs=["witness:planner"],
        anti_echo_quarantine=True,
    )
    decision, _ = request_promotion(capsule, review_approved=True)

    assert capsule.event_stage == ArqStage.QUARANTINED
    assert events[-1].event_type.value == "arq.quarantined"
    assert decision.allowed is False
    assert decision.target_stage == ArqStage.QUARANTINED
    assert "ARQ_ANTI_ECHO_QUARANTINE" in decision.reason_codes


def test_slot_b_cannot_rescue_slot_a_failure():
    capsule, _ = detect_deviation(
        profile_id=ArqProfileId.RAG,
        detected_by=DetectorLayer.L3,
        boundary_id="boundary:rag",
        capsule_id="capsule-slot-b",
    )
    capsule, _ = classify_capsule(
        capsule,
        deviation_class=DeviationClass.EXPLORATORY,
        recommended_action=Recommendation.CANDIDATE,
        witness_refs=["witness:rag"],
        slot=Slot.B,
        slot_a_valid=False,
    )
    decision, _ = request_promotion(capsule, review_approved=True)

    assert decision.allowed is False
    assert "ARQ_SLOT_A_FAILURE" in decision.reason_codes


def test_trust_or_budget_failure_enters_fail_closed():
    capsule, _ = detect_deviation(
        profile_id=ArqProfileId.VISION,
        detected_by=DetectorLayer.L2,
        boundary_id="boundary:vision",
        capsule_id="capsule-fail",
    )
    capsule, events = classify_capsule(
        capsule,
        deviation_class=DeviationClass.QUARANTINED,
        recommended_action=Recommendation.CANDIDATE,
        trust_valid=False,
    )

    assert capsule.event_stage == ArqStage.FAIL_CLOSED
    assert capsule.reason_codes == ("ARQ_TRUST_INVALID",)
    assert events[-1].event_type.value == "arq.fail_closed"


def test_arq_store_persists_capsules_and_events(tmp_path):
    capsule, detected_event = detect_deviation(
        profile_id=ArqProfileId.PLANNER,
        detected_by=DetectorLayer.L1,
        boundary_id="boundary:planner",
        capsule_id="capsule-store",
    )
    capsule, events = classify_capsule(
        capsule,
        deviation_class=DeviationClass.NEUTRAL,
        recommended_action=Recommendation.OBSERVE,
    )
    store = ArqStore(tmp_path)
    store.save_capsule(capsule)
    store.append_events((detected_event, *events))

    loaded = ArqStore(tmp_path).load_capsule("capsule-store")
    loaded_events = ArqStore(tmp_path).load_events()

    assert loaded["event_stage"] == "observed"
    assert [event["event_type"] for event in loaded_events] == [
        "arq.detected",
        "arq.classified",
        "arq.observe_window_opened",
    ]
    assert store.manifest()["memory_promotion_wired"] is False
