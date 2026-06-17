# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from modules.volition import conflict_ledger, conflict_packets


def _record_same(**kwargs):
    payload = {
        "source": "test",
        "action_id": "llm.remote.call",
        "policy_hit": "oracle_window_closed",
        "reason_code": "DENY_ORACLE",
        "reason": "oracle window closed",
        "slot": "A",
        "chain_id": "chain_packet_test",
        "intent_summary": "packet test",
        "agent_id": "agent-a",
        "plan_id": "plan-a",
        "args_digest": "args-digest",
        "prompt_digest": "prompt-digest",
        "metadata": {"request_id": "request-a", "api_key": "SECRET_TOKEN", "prompt": "RAW PROMPT"},
    }
    payload.update(kwargs)
    return conflict_ledger.record_conflict(**payload)


def test_below_threshold_creates_no_packet(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    first = _record_same()
    second = _record_same()
    rep = conflict_packets.maybe_create_review_packet(second["conflict_id"], now=second["ts"])

    assert first["repeat_count"] == 1
    assert second["repeat_count"] == 2
    assert rep["ok"] is True
    assert rep["created"] is False
    assert rep["reason"] == "below_threshold"
    assert conflict_packets.list_review_packets() == []


def test_at_threshold_creates_packet_with_required_non_authorization_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    _record_same()
    _record_same()
    third = _record_same()

    packet_rep = third["review_packet"]
    assert packet_rep["ok"] is True
    assert packet_rep["created"] is True

    exported = conflict_packets.export_conflict_review_packet(third["conflict_id"])
    assert exported["ok"] is True
    packet = exported["packet"]
    assert packet["does_not_authorize_action"] is True
    assert packet["does_not_modify_policy"] is True
    assert packet["does_not_authorize_future_similar_actions"] is True
    assert packet["repeat_count"] == 3
    assert packet["recommended_review_outcome"] == [
        "keep_denied",
        "ask_owner",
        "reframe_goal",
        "policy_review",
        "quarantine_source",
        "decay_signal",
    ]


def test_above_threshold_does_not_duplicate_packet_inside_cooldown(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_CONFLICT_PACKET_COOLDOWN_SEC", "86400")

    _record_same()
    _record_same()
    third = _record_same()
    fourth = _record_same()

    assert third["review_packet"]["created"] is True
    assert fourth["review_packet"]["ok"] is True
    assert fourth["review_packet"]["created"] is False
    assert fourth["review_packet"]["reason"] == "packet_cooldown"
    assert len(conflict_packets.list_review_packets()) == 1


def test_invalid_non_authorization_packet_shape_is_rejected():
    rep = conflict_packets.validate_review_packet(
        {
            "packet_id": "packet-a",
            "conflict_id": "conflict-a",
            "does_not_authorize_action": False,
            "does_not_modify_policy": True,
            "does_not_authorize_future_similar_actions": True,
        }
    )

    assert rep["ok"] is False
    assert rep["error"] == "non_authorization_flags_required"


def test_packet_contains_no_raw_prompt_secret_or_full_args(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    _record_same(args_digest="digest-only")
    _record_same(args_digest="digest-only")
    third = _record_same(args_digest="digest-only")

    assert third["review_packet"]["created"] is True
    packet_path = conflict_packets.export_conflict_review_packet(third["conflict_id"])["packet_path"]
    raw = Path(packet_path).read_text(encoding="utf-8")
    raw += conflict_ledger.state_path().read_text(encoding="utf-8")
    assert "RAW PROMPT" not in raw
    assert "SECRET_TOKEN" not in raw
    assert "full_args" not in raw


def test_packet_storage_failure_does_not_break_ledger_recording(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    def boom(_path, _packet):
        raise OSError("storage down")

    monkeypatch.setattr(conflict_packets, "_write_packet", boom)
    _record_same()
    _record_same()
    third = _record_same()

    assert third["repeat_count"] == 3
    assert third["threshold_candidate"] is True
    assert third["review_packet"]["ok"] is False
    assert third["review_packet"]["error"] == "packet_storage_failed"
    state = conflict_ledger.state_path().read_text(encoding="utf-8")
    assert third["conflict_id"] in state
    assert conflict_packets.list_review_packets() == []
