from pathlib import Path

from modules.glitch_stack import (
    GlitchM1Store,
    Lane,
    RuntimeLockType,
    build_m1_bundle_from_quarantine_row,
    lock_type_from_quarantine_row,
    persist_m1_bundle,
)


def _active_quarantine_row():
    return {
        "agent_id": "agent.alpha",
        "active": True,
        "since_ts": 1_775_000_000,
        "event_id": "evt-alpha",
        "kind": "SPEC_MISMATCH",
        "severity": "HIGH",
        "reason_code": "TAMPER_SUSPECT",
        "template_id": "builder.v1",
        "computed_hash": "computed-hash",
        "stored_hash": "stored-hash",
        "added": ["unsafe.action"],
        "removed": [],
        "challenge_open_ts": 1_775_000_000,
        "challenge_deadline_ts": 1_775_003_600,
        "challenge_sec": 3600,
    }


def test_active_quarantine_row_builds_dry_run_m1_bundle(tmp_path):
    result = build_m1_bundle_from_quarantine_row(_active_quarantine_row())

    assert result.ok is True
    assert result.lock_type == RuntimeLockType.INTEGRITY_LOCK
    assert result.glitch is not None
    assert result.research is not None
    assert result.glitch.status.lane == Lane.RUNTIME
    assert result.glitch.status.executable is False
    assert result.research.status.lane == Lane.RESEARCH
    assert result.research.status.executable is False
    assert [event.event_type for event in result.events] == [
        "RuntimeCollisionRegistered",
        "GlitchNodeCreated",
        "CollisionWitnessAttached",
        "ChallengeOpened",
        "ResearchNodeDerived",
    ]

    paths = persist_m1_bundle(
        GlitchM1Store(tmp_path),
        glitch=result.glitch,
        research=result.research,
        events=result.events,
    )
    assert Path(paths["events_path"]).exists()


def test_inactive_quarantine_row_is_denied_without_events():
    result = build_m1_bundle_from_quarantine_row({"agent_id": "agent.alpha", "active": False})

    assert result.ok is False
    assert result.decision.allowed is False
    assert result.decision.rule_code == "QUARANTINE_ROW_INACTIVE"
    assert result.events == ()
    assert result.glitch is None
    assert result.research is None


def test_quarantine_adapter_requires_witness_for_challenge_or_research():
    result = build_m1_bundle_from_quarantine_row(_active_quarantine_row(), witness_id="")

    assert result.ok is False
    assert result.decision.rule_code == "QUARANTINE_ADAPTER_WITNESS_REQUIRED"
    assert result.events == ()


def test_quarantine_lock_type_mapping_is_conservative():
    assert (
        lock_type_from_quarantine_row({"reason_code": "ALLOWLIST_CHANGED"})
        == RuntimeLockType.CONTINUITY_LOCK
    )
    assert (
        lock_type_from_quarantine_row({"reason_code": "RBAC_PRIVILEGE_ESCALATION"})
        == RuntimeLockType.PRIVILEGE_LOCK
    )
    assert lock_type_from_quarantine_row({"reason_code": "UNKNOWN"}) == RuntimeLockType.CAUTION_LOCK
