from modules.beacon_profile import (
    AssuranceClass,
    BeaconBundle,
    BeaconIssuer,
    BeaconProfileStore,
    ChallengePolicy,
    ContinuityEvidence,
    ContinuityWindow,
    IdentityLineage,
    PrivacyPolicy,
    PrivilegeContinuity,
    classify_beacon_bundle,
)


def _bundle(**overrides):
    base = {
        "beacon_id": "beacon:ester",
        "issued_at": "2026-04-26T00:00:00+00:00",
        "assurance_class_claimed": AssuranceClass.CLASS3_VERIFIED_ENTITY,
        "issuer": BeaconIssuer(entity_id="entity:ester", key_id="key:ester:1"),
        "identity": IdentityLineage(
            lineage_id="lineage:ester",
            rotation_declared=True,
            provider_independent=True,
            anchor_cosign_present=True,
        ),
        "continuity": ContinuityEvidence(
            continuity_window=ContinuityWindow(
                start_at="2026-04-01T00:00:00+00:00",
                end_at="2026-04-26T00:00:00+00:00",
            ),
            memory_bound=True,
            privilege_continuity=PrivilegeContinuity.STABLE,
            behavior_markers=("bounded_refusal", "stable_l4_response", "uncertainty_marked"),
        ),
        "challenge": ChallengePolicy(
            challengeable=True,
            witness_refs=("CE:1", "OP:1"),
            window_policy="bounded",
            arbiter_policy_ref="arl:review",
        ),
        "privacy": PrivacyPolicy(raw_memory_disclosed=False),
        "hash_alg": "sha256",
        "sig_alg": "ed25519",
        "payload_hash": "hash:payload",
        "record_sig": "sig:record",
    }
    base.update(overrides)
    return BeaconBundle(**base)


def test_verified_entity_requires_all_three_beacon_layers_and_persists(tmp_path):
    bundle = _bundle()
    decision = classify_beacon_bundle(bundle, decision_id="beacon-decision-1")
    store = BeaconProfileStore(tmp_path)
    store.save_bundle(bundle)
    store.append_decision(decision)

    loaded_bundle = BeaconProfileStore(tmp_path).load_bundle("beacon:ester")
    loaded_decisions = BeaconProfileStore(tmp_path).load_decisions()

    assert decision.verified_class == AssuranceClass.CLASS3_VERIFIED_ENTITY
    assert decision.slot_a.ok is True
    assert decision.slot_b.ok is True
    assert "bounded_delegation" in decision.privileges
    assert loaded_bundle["schema_version"] == "beacon-0.1"
    assert loaded_decisions[0]["verified_class"] == "class3"
    assert store.manifest()["kg_activity_beacons"] is False
    assert store.manifest()["raw_memory_required"] is False


def test_slot_a_failure_forces_class0_even_if_continuity_sounds_good():
    bundle = _bundle(record_sig="")

    decision = classify_beacon_bundle(bundle)

    assert decision.verified_class == AssuranceClass.CLASS0_UNKNOWN
    assert decision.slot_a.ok is False
    assert decision.slot_b.ok is True
    assert "BEACON_RECORD_SIG_REQUIRED" in decision.reason_codes


def test_missing_challenge_downgrades_high_assurance_claim_to_class0():
    bundle = _bundle(challenge=ChallengePolicy(challengeable=False, witness_refs=()))

    decision = classify_beacon_bundle(bundle)

    assert decision.verified_class == AssuranceClass.CLASS0_UNKNOWN
    assert "BEACON_CHALLENGE_REQUIRED" in decision.reason_codes
    assert "BEACON_WITNESS_REQUIRED" in decision.reason_codes


def test_tool_oracle_component_remains_class1():
    bundle = _bundle(
        assurance_class_claimed=AssuranceClass.CLASS1_TOOL_ORACLE_COMPONENT,
        continuity=ContinuityEvidence(memory_bound=False),
        challenge=ChallengePolicy(challengeable=False, witness_refs=()),
    )

    decision = classify_beacon_bundle(bundle)

    assert decision.verified_class == AssuranceClass.CLASS1_TOOL_ORACLE_COMPONENT
    assert decision.privileges == ("tool_use", "oracle_query")


def test_continuity_gap_rolls_back_to_provisional_class2():
    bundle = _bundle(
        continuity=ContinuityEvidence(
            continuity_window=ContinuityWindow(
                start_at="2026-04-01T00:00:00+00:00",
                end_at="2026-04-26T00:00:00+00:00",
            ),
            memory_bound=False,
            privilege_continuity=PrivilegeContinuity.LIMITED,
            behavior_markers=("bounded_refusal",),
            uncertainty_markers=("continuity_partial",),
        )
    )

    decision = classify_beacon_bundle(bundle)

    assert decision.slot_a.ok is True
    assert decision.slot_b.ok is False
    assert decision.verified_class == AssuranceClass.CLASS2_PROVISIONAL_ENTITY
    assert "BEACON_MEMORY_BOUND_REQUIRED" in decision.reason_codes
    assert "BEACON_UNCERTAINTY_MARKED" in decision.reason_codes


def test_raw_memory_disclosure_is_not_accepted_by_default():
    bundle = _bundle(privacy=PrivacyPolicy(raw_memory_disclosed=True))

    decision = classify_beacon_bundle(bundle)

    assert decision.verified_class == AssuranceClass.CLASS0_UNKNOWN
    assert decision.raw_memory_disclosure_accepted is False
    assert "BEACON_RAW_MEMORY_DISCLOSED" in decision.reason_codes
