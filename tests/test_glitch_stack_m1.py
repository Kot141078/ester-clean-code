import json

import pytest

from modules.glitch_stack import (
    EvidenceRecord,
    EvidenceState,
    GlitchValidationError,
    Lane,
    NodeKind,
    NodeRef,
    ReopenabilityState,
    ResearchNode,
    RuntimeLockType,
    StatusTuple,
    TimeWindow,
    WitnessRef,
    attach_collision_witness,
    authorize_runtime_from_evidence,
    derive_research_node,
    open_collision_challenge_window,
    register_runtime_collision,
    store_research_node,
    validate_research_node,
    validate_transition,
)


def test_runtime_collision_becomes_non_executable_glitch_node():
    glitch, events = register_runtime_collision(
        collision_id="collision-001",
        lock_type=RuntimeLockType.EVIDENCE_LOCK,
        summary="runtime evidence collision",
        occurred_at="2026-04-26T00:00:00+00:00",
    )

    assert glitch.node_ref.kind == NodeKind.GLITCH_NODE
    assert glitch.status.lane == Lane.RUNTIME
    assert glitch.status.executable is False
    assert [event.event_type for event in events] == [
        "RuntimeCollisionRegistered",
        "GlitchNodeCreated",
    ]


def test_witnessed_challenge_derives_quarantined_research_node(tmp_path):
    glitch, _ = register_runtime_collision(
        collision_id="collision-002",
        lock_type=RuntimeLockType.TRUST_LOCK,
    )
    witness = WitnessRef("witness-local-1", signature_ref="sig:test")
    witnessed, witness_event = attach_collision_witness(
        glitch,
        witness,
        evidence_id="evidence-002",
        evidence_state=EvidenceState.WITNESSED,
    )
    challenged, challenge_event = open_collision_challenge_window(
        witnessed,
        TimeWindow(opened_at="2026-04-26T00:00:00+00:00"),
    )
    research, derived_event = derive_research_node(
        challenged,
        summary="preserved unresolved research lane",
    )
    stored_path = store_research_node(research, tmp_path)

    assert witness_event.event_type == "CollisionWitnessAttached"
    assert challenge_event.event_type == "ChallengeOpened"
    assert derived_event.event_type == "ResearchNodeDerived"
    assert research.status.lane == Lane.RESEARCH
    assert research.status.executable is False
    assert research.source_glitch_ref.kind == NodeKind.GLITCH_NODE
    assert research.status.reopenability == ReopenabilityState.EVIDENCE_REQUIRED

    payload = json.loads(stored_path.read_text(encoding="utf-8"))
    assert payload["node_ref"]["kind"] == "ResearchNode"
    assert payload["source_glitch_ref"]["kind"] == "GlitchNode"


def test_research_to_runtime_shortcut_is_blocked():
    source = StatusTuple(lane=Lane.RESEARCH, reopenability=ReopenabilityState.EVIDENCE_REQUIRED)
    target = StatusTuple(lane=Lane.RUNTIME, executable=False)

    decision = validate_transition(source, target)

    assert decision.allowed is False
    assert decision.rule_code == "TRANSITION_RESEARCH_TO_RUNTIME_FORBIDDEN"


def test_research_executable_shortcut_is_blocked_by_status_validation():
    source = StatusTuple(lane=Lane.RESEARCH, reopenability=ReopenabilityState.EVIDENCE_REQUIRED)
    target = StatusTuple(lane=Lane.RESEARCH, executable=True)

    decision = validate_transition(source, target)

    assert decision.allowed is False
    assert decision.rule_code == "TRANSITION_RESEARCH_EXECUTABLE_FORBIDDEN"


def test_cinematic_projection_cannot_create_runtime_truth():
    source = StatusTuple(lane=Lane.CINEMATIC, evidence_state=EvidenceState.CINEMATIC_ONLY)
    target = StatusTuple(lane=Lane.RUNTIME)

    decision = validate_transition(source, target)

    assert decision.allowed is False
    assert decision.rule_code == "TRANSITION_CINEMATIC_TO_RUNTIME_FORBIDDEN"


def test_signature_does_not_imply_legitimacy():
    evidence = EvidenceRecord(
        evidence_id="signed-only",
        state=EvidenceState.SIGNED,
        witness_ref=WitnessRef("witness-local-2"),
        signer="witness-local-2",
    )

    decision = authorize_runtime_from_evidence(evidence)

    assert decision.allowed is False
    assert decision.rule_code == "SIGNATURE_NOT_LEGITIMACY"


def test_invalid_executable_research_node_is_rejected():
    research_ref = NodeRef("research:bad", NodeKind.RESEARCH_NODE, Lane.RESEARCH)
    source_ref = NodeRef("glitch:source", NodeKind.GLITCH_NODE, Lane.RUNTIME)
    status = StatusTuple(
        lane=Lane.RESEARCH,
        executable=True,
        reopenability=ReopenabilityState.EVIDENCE_REQUIRED,
    )

    research_node = ResearchNode(
        node_ref=research_ref,
        source_glitch_ref=source_ref,
        status=status,
        summary="bad shortcut",
    )
    issues = validate_research_node(research_node)

    assert research_node.status.executable is True
    assert any(issue.rule_code == "RESEARCH_EXECUTABLE" for issue in issues)


def test_research_requires_witnessed_source_glitch():
    glitch, _ = register_runtime_collision(
        collision_id="collision-003",
        lock_type=RuntimeLockType.INTEGRITY_LOCK,
    )

    with pytest.raises(GlitchValidationError) as exc:
        derive_research_node(glitch, summary="should not derive without witness")

    assert any(issue.rule_code == "RESEARCH_WITNESS_REQUIRED" for issue in exc.value.issues)
