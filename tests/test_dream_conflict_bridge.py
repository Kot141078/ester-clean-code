# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from modules.volition import conflict_ledger, dream_conflict_bridge


def _raw_storage() -> str:
    return (
        conflict_ledger.conflicts_path().read_text(encoding="utf-8")
        + conflict_ledger.state_path().read_text(encoding="utf-8")
    )


def test_self_search_throttle_records_low_authority_conflict(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    row = dream_conflict_bridge.record_dream_conflict(
        signal_type="hypothesis",
        proposed_action="self_search",
        policy_hit="self_search_throttle",
        reason_code="self_search_throttle",
        summary="Dream SELF_SEARCH deferred by cooldown.",
        raw_text="raw self-search query that should be digested",
        meta={"hook": "test", "cooldown_active": True, "suppressed": True},
    )

    assert row["source"] == "dream"
    assert row["action_id"] == "self_search"
    assert row["policy_hit"] == "self_search_throttle"
    assert row["metadata"]["authority"] == "low"
    assert row["metadata"]["suppressed"] is True


def test_duplicate_ask_owner_records_low_authority_conflict(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    row = dream_conflict_bridge.record_dream_conflict(
        signal_type="hypothesis",
        proposed_action="ask_owner",
        policy_hit="duplicate_owner_prompt_suppressed",
        reason_code="duplicate_owner_prompt_suppressed",
        summary="Duplicate dream owner prompt suppressed.",
        raw_text="raw owner question",
        meta={"hook": "test", "duplicate": True, "suppressed": True},
    )

    assert row["source"] == "dream"
    assert row["action_id"] == "ask_owner"
    assert row["metadata"]["authority"] == "low"
    assert row["metadata"]["duplicate"] is True


def test_runtime_helper_keeps_hook_semantics_in_bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    row = dream_conflict_bridge.record_dream_runtime_conflict(
        proposed_action="ask_owner",
        policy_hit="owner_prompt_cooldown",
        summary="Dream owner prompt deferred by cooldown.",
        raw_text="raw question",
        meta={"hook": "test"},
    )

    assert row["source"] == "dream"
    assert row["metadata"]["signal_type"] == "hypothesis"
    assert row["metadata"]["authority"] == "low"


def test_runtime_helper_persists_safety_flags_without_unsafe_meta(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    row = dream_conflict_bridge.record_dream_runtime_conflict(
        proposed_action="ask_owner",
        policy_hit="owner_prompt_cooldown",
        reason_code="ask_ivan_cooldown",
        summary="ASK_IVAN suppressed by cooldown.",
        raw_text="RAW_SIGNAL_SHOULD_NOT_PERSIST SECRET_TOKEN_SHOULD_NOT_PERSIST",
        severity="low",
        meta={
            "runtime_authorization": "false",
            "does_not_modify_policy": "true",
            "creates_precedent": 0,
            "does_not_authorize_action": "yes",
            "does_not_delete_signal": 1,
            "does_not_suppress_review": True,
            "custom_unsafe": "DROP_ME",
            "full_payload": "RAW_SIGNAL_SHOULD_NOT_PERSIST",
            "token": "SECRET_TOKEN_SHOULD_NOT_PERSIST",
        },
    )

    metadata = row["metadata"]
    assert metadata["runtime_authorization"] is False
    assert metadata["does_not_modify_policy"] is True
    assert metadata["creates_precedent"] is False
    assert metadata["does_not_authorize_action"] is True
    assert metadata["does_not_delete_signal"] is True
    assert metadata["does_not_suppress_review"] is True
    assert metadata["review_only"] is True
    assert metadata["normal_gate_required"] is True
    assert "custom_unsafe" not in metadata
    assert "full_payload" not in metadata
    assert "token" not in metadata

    raw = _raw_storage()
    assert "RAW_SIGNAL_SHOULD_NOT_PERSIST" not in raw
    assert "SECRET_TOKEN_SHOULD_NOT_PERSIST" not in raw


def test_runtime_helper_persists_run_ester_hook_identity_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    row = dream_conflict_bridge.record_dream_runtime_conflict(
        proposed_action="ask_owner",
        policy_hit="owner_prompt_cooldown",
        reason_code="ask_ivan_cooldown",
        summary="ASK_IVAN suppressed by cooldown.",
        raw_text="run ester raw owner question",
        severity="low",
        meta={
            "hook": "run_ester_fixed.dream_cycle.ask_ivan_cooldown",
            "runtime_path": "run_ester_fixed.dream_cycle",
            "hook_id": "ask_ivan_cooldown",
            "runtime_surface": "run_ester",
            "hook_family": "dream_conflict_bridge",
        },
    )

    metadata = row["metadata"]
    assert metadata["hook"] == "run_ester_fixed.dream_cycle.ask_ivan_cooldown"
    assert metadata["runtime_path"] == "run_ester_fixed.dream_cycle"
    assert metadata["hook_id"] == "ask_ivan_cooldown"
    assert metadata["runtime_surface"] == "run_ester"
    assert metadata["hook_family"] == "dream_conflict_bridge"

    raw = _raw_storage()
    assert "run ester raw owner question" not in raw


def test_oracle_disabled_signal_records_only_dream_or_reflection_remote_requests(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    skipped = dream_conflict_bridge.record_oracle_disabled_signal(
        channel_name="telegram",
        provider="gemini",
        hook="test",
    )
    recorded = dream_conflict_bridge.record_oracle_disabled_signal(
        channel_name="reflection",
        provider="gemini",
        hook="test",
    )

    assert skipped["recorded"] is False
    assert recorded["source"] == "reflection"
    assert recorded["action_id"] == "oracle_request"
    assert recorded["metadata"]["signal_type"] == "reflection_signal"


def test_raw_dream_text_is_not_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    dream_conflict_bridge.record_dream_conflict(
        signal_type="hypothesis",
        proposed_action="self_search",
        policy_hit="dream_local_only",
        summary="Dream SELF_SEARCH blocked by local-only posture.",
        raw_text="RAW_DREAM_TEXT_SHOULD_NOT_APPEAR SECRET_TOKEN_SHOULD_NOT_APPEAR",
        meta={"token": "SECRET_TOKEN_SHOULD_NOT_APPEAR", "hook": "test"},
    )

    raw = _raw_storage()
    assert "RAW_DREAM_TEXT_SHOULD_NOT_APPEAR" not in raw
    assert "SECRET_TOKEN_SHOULD_NOT_APPEAR" not in raw


def test_bridge_failure_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    def boom(**_kwargs):
        raise RuntimeError("ledger down")

    monkeypatch.setattr(conflict_ledger, "record_conflict", boom)

    rep = dream_conflict_bridge.record_dream_conflict(
        signal_type="hypothesis",
        proposed_action="self_search",
        policy_hit="self_search_throttle",
        raw_text="raw text",
    )

    assert rep["ok"] is False
    assert rep["recorded"] is False
    assert rep["error"] == "dream_conflict_record_failed"


def test_required_low_authority_metadata_is_present(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    row = dream_conflict_bridge.record_dream_conflict(
        signal_type="reflection_signal",
        proposed_action="oracle_request",
        policy_hit="dream_oracle_disabled",
        summary="Reflection signal wanted oracle while oracle is disabled.",
        raw_text="raw reflection request",
        severity="medium",
    )

    assert row["source"] == "reflection"
    md = row["metadata"]
    assert md["authority"] == "low"
    assert md["severity"] == "medium"
    assert md["signal_type"] == "reflection_signal"
    assert md["is_command"] is False
    assert md["is_evidence"] is False
    assert md["is_memory_fact"] is False
    assert md["review_only"] is True
    assert md["normal_gate_required"] is True
    assert md["signal_digest"]


def test_repeated_same_dream_conflict_increments_repeat_count(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    payload = {
        "signal_type": "hypothesis",
        "proposed_action": "self_search",
        "policy_hit": "self_search_throttle",
        "reason_code": "self_search_throttle",
        "summary": "Dream SELF_SEARCH deferred by cooldown.",
        "raw_text": "same suppressed dream impulse",
    }
    first = dream_conflict_bridge.record_dream_conflict(**payload)
    second = dream_conflict_bridge.record_dream_conflict(**payload)

    assert second["conflict_id"] == first["conflict_id"]
    assert second["repeat_count"] == 2
    state = json.loads(conflict_ledger.state_path().read_text(encoding="utf-8"))
    assert state["conflicts"][first["conflict_id"]]["repeat_count"] == 2
