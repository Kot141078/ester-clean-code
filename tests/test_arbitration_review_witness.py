from modules.arbitration_review import (
    ArlWitnessLedger,
    ConflictClass,
    ScopeRef,
    event_hash,
    open_dispute,
    payload_hash,
    verify_witness_footprint,
)


def test_arl_witness_ledger_records_hash_chained_footprints(tmp_path):
    _, events = open_dispute(
        conflict_class=ConflictClass.RUNTIME_COLLISION,
        scope_ref=ScopeRef("glitch:collision-1", "GlitchNode"),
        reason_code="runtime_collision_registered",
        dispute_id="dispute-witness-1",
        occurred_at="2026-04-26T00:00:00+00:00",
    )
    ledger = ArlWitnessLedger(tmp_path)

    footprints = ledger.append_events(events, witness_id="witness:test")
    rows = ArlWitnessLedger(tmp_path).load_footprints()
    report = ArlWitnessLedger(tmp_path).verify_chain()

    assert len(footprints) == 2
    assert [row["event_type"] for row in rows] == ["arl.dispute_opened", "arl.state_changed"]
    assert rows[0]["prev_hash"] == ""
    assert rows[1]["prev_hash"] == rows[0]["footprint_hash"]
    assert report["ok"] is True
    assert report["footprints"] == 2
    assert report["last_hash"] == rows[1]["footprint_hash"]


def test_arl_witness_footprint_hashes_match_event_and_payload(tmp_path):
    _, events = open_dispute(
        conflict_class=ConflictClass.EVIDENCE_CONFLICT,
        scope_ref=ScopeRef("evidence:1", "EvidenceRecord"),
        reason_code="evidence_conflict",
        dispute_id="dispute-witness-2",
    )
    footprint = ArlWitnessLedger(tmp_path).append_event(events[0], witness_id="witness:test")

    assert footprint.event_hash == event_hash(events[0])
    assert footprint.payload_hash == payload_hash(events[0])
    assert verify_witness_footprint(footprint)["ok"] is True


def test_arl_witness_chain_detects_tampering(tmp_path):
    _, events = open_dispute(
        conflict_class=ConflictClass.UNKNOWN,
        scope_ref=ScopeRef("scope:1", "unknown"),
        reason_code="opened",
        dispute_id="dispute-witness-3",
    )
    ledger = ArlWitnessLedger(tmp_path)
    ledger.append_events(events, witness_id="witness:test")

    lines = ledger.witness_path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("dispute-witness-3", "dispute-tampered")
    ledger.witness_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = ledger.verify_chain()

    assert report["ok"] is False
    assert report["error_code"] == "ARL_WITNESS_FOOTPRINT_HASH_MISMATCH"
    assert report["index"] == 0
