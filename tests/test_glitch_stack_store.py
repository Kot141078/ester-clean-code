import json
from pathlib import Path

from modules.glitch_stack import (
    EvidenceState,
    GlitchM1Store,
    RuntimeLockType,
    TimeWindow,
    WitnessRef,
    attach_collision_witness,
    derive_research_node,
    open_collision_challenge_window,
    persist_m1_bundle,
    register_runtime_collision,
)


def _m1_bundle():
    glitch, collision_events = register_runtime_collision(
        collision_id="collision-store-001",
        lock_type=RuntimeLockType.CONTINUITY_LOCK,
    )
    glitch, witness_event = attach_collision_witness(
        glitch,
        WitnessRef("witness-store-1"),
        evidence_id="evidence-store-001",
        evidence_state=EvidenceState.WITNESSED,
    )
    glitch, challenge_event = open_collision_challenge_window(
        glitch,
        TimeWindow(opened_at="2026-04-26T00:00:00+00:00"),
    )
    research, derived_event = derive_research_node(
        glitch,
        summary="stored quarantined research node",
    )
    return glitch, research, (*collision_events, witness_event, challenge_event, derived_event)


def test_glitch_m1_store_persists_nodes_and_events_across_instances(tmp_path):
    glitch, research, events = _m1_bundle()
    store = GlitchM1Store(tmp_path)

    paths = persist_m1_bundle(store, glitch=glitch, research=research, events=events)
    reopened = GlitchM1Store(tmp_path)

    assert paths["glitch_path"]
    assert paths["research_path"]
    assert (tmp_path / "glitch_m1" / "events.jsonl").exists()
    assert len(reopened.load_events()) == 5
    assert [event["event_type"] for event in reopened.load_events()] == [
        "RuntimeCollisionRegistered",
        "GlitchNodeCreated",
        "CollisionWitnessAttached",
        "ChallengeOpened",
        "ResearchNodeDerived",
    ]


def test_glitch_m1_store_keeps_research_lane_separate(tmp_path):
    glitch, research, events = _m1_bundle()
    store = GlitchM1Store(tmp_path)
    paths = persist_m1_bundle(store, glitch=glitch, research=research, events=events)

    manifest = json.loads((tmp_path / "glitch_m1" / "manifest.json").read_text(encoding="utf-8"))
    glitch_path = Path(paths["glitch_path"])
    research_path = Path(paths["research_path"])
    glitch_payload = json.loads(glitch_path.read_text(encoding="utf-8"))
    research_payload = json.loads(research_path.read_text(encoding="utf-8"))

    assert manifest["schema"] == "ester.glitch_m1.store.v1"
    assert manifest["research_lane_separate"] is True
    assert "research_nodes" in research_path.parts
    assert "glitch_nodes" in glitch_path.parts
    assert glitch_payload["status"]["lane"] == "runtime"
    assert research_payload["status"]["lane"] == "research"
    assert research_payload["status"]["executable"] is False
