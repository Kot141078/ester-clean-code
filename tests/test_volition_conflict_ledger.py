# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from modules.volition import conflict_ledger


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_first_record_creates_conflict_id_and_state(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    row = conflict_ledger.record_conflict(
        source="test",
        action_id="local.search",
        policy_hit="DENY_NETWORK",
        reason_code="DENY_NETWORK",
        reason="network disabled",
        agent_id="agent-a",
        args_digest="args-digest-1",
        metadata={"args_digest": "args-digest-1", "api_key": "SECRET_TOKEN", "prompt": "RAW PROMPT"},
    )

    assert row["conflict_id"].startswith("conflict_")
    assert row["status"] == "held"
    assert row["repeat_count"] == 1
    assert row["threshold_candidate"] is False

    rows = _read_jsonl(conflict_ledger.conflicts_path())
    assert rows[0]["conflict_id"] == row["conflict_id"]
    state = json.loads(conflict_ledger.state_path().read_text(encoding="utf-8"))
    assert state["conflicts"][row["conflict_id"]]["repeat_count"] == 1

    raw = conflict_ledger.conflicts_path().read_text(encoding="utf-8")
    raw += conflict_ledger.state_path().read_text(encoding="utf-8")
    assert "SECRET_TOKEN" not in raw
    assert "RAW PROMPT" not in raw


def test_metadata_safety_flags_are_boolean_and_whitelist_stays_narrow(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    row = conflict_ledger.record_conflict(
        source="dream",
        action_id="ask_owner",
        policy_hit="owner_prompt_cooldown",
        reason_code="ask_ivan_cooldown",
        args_digest="safety-flags",
        metadata={
            "runtime_authorization": "false",
            "does_not_modify_policy": "true",
            "creates_precedent": 0,
            "does_not_authorize_action": 1,
            "does_not_delete_signal": "yes",
            "does_not_suppress_review": "on",
            "normal_gate_required": "true",
            "review_only": "false",
            "custom_unsafe": "DROP_ME",
            "payload": "RAW_PAYLOAD_SHOULD_NOT_PERSIST",
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
    assert metadata["normal_gate_required"] is True
    assert metadata["review_only"] is False
    assert "custom_unsafe" not in metadata
    assert "payload" not in metadata
    assert "token" not in metadata

    raw = conflict_ledger.conflicts_path().read_text(encoding="utf-8")
    raw += conflict_ledger.state_path().read_text(encoding="utf-8")
    assert "DROP_ME" not in raw
    assert "RAW_PAYLOAD_SHOULD_NOT_PERSIST" not in raw
    assert "SECRET_TOKEN_SHOULD_NOT_PERSIST" not in raw


def test_hook_identity_metadata_persists_but_does_not_affect_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    first = conflict_ledger.record_conflict(
        source="dream",
        action_id="ask_owner",
        policy_hit="owner_prompt_cooldown",
        reason_code="ask_ivan_cooldown",
        args_digest="same-hook-identity-test",
        metadata={
            "runtime_path": "run_ester_fixed.dream_cycle",
            "hook_id": "ask_ivan_cooldown",
            "runtime_surface": "run_ester",
            "hook_family": "dream_conflict_bridge",
        },
    )
    second = conflict_ledger.record_conflict(
        source="dream",
        action_id="ask_owner",
        policy_hit="owner_prompt_cooldown",
        reason_code="ask_ivan_cooldown",
        args_digest="same-hook-identity-test",
        metadata={
            "runtime_path": "telegram_bot.dream_cycle",
            "hook_id": "telegram_ask_ivan_defer",
            "runtime_surface": "telegram_listener",
            "hook_family": "dream_conflict_bridge",
        },
    )

    assert first["metadata"]["runtime_path"] == "run_ester_fixed.dream_cycle"
    assert first["metadata"]["hook_id"] == "ask_ivan_cooldown"
    assert first["metadata"]["runtime_surface"] == "run_ester"
    assert first["metadata"]["hook_family"] == "dream_conflict_bridge"
    assert second["metadata"]["runtime_path"] == "telegram_bot.dream_cycle"
    assert second["metadata"]["hook_id"] == "telegram_ask_ivan_defer"
    assert second["metadata"]["runtime_surface"] == "telegram_listener"
    assert second["metadata"]["hook_family"] == "dream_conflict_bridge"
    assert second["conflict_id"] == first["conflict_id"]
    assert second["repeat_count"] == 2


def test_hook_identity_metadata_rejects_paths_controls_and_unsafe_payloads(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    long_surface = "surface_" + ("x" * 200)

    row = conflict_ledger.record_conflict(
        source="dream",
        action_id="ask_owner",
        policy_hit="owner_prompt_cooldown",
        reason_code="ask_ivan_cooldown",
        args_digest="identity-sanitize",
        metadata={
            "runtime_path": r"C:\Users\kotov\secret\listener.py",
            "hook_id": "ask\nivan\tcooldown",
            "runtime_surface": long_surface,
            "hook_family": 'Traceback (most recent call last): File "secret.py"',
            "custom_unsafe": "DROP_ME",
            "raw_payload": "RAW_PAYLOAD_SHOULD_NOT_PERSIST",
            "token": "SECRET_TOKEN_SHOULD_NOT_PERSIST",
        },
    )

    metadata = row["metadata"]
    assert "runtime_path" not in metadata
    assert metadata["hook_id"] == "ask ivan cooldown"
    assert metadata["runtime_surface"] == long_surface[:120]
    assert "hook_family" not in metadata
    assert "custom_unsafe" not in metadata
    assert "raw_payload" not in metadata
    assert "token" not in metadata

    raw = conflict_ledger.conflicts_path().read_text(encoding="utf-8")
    raw += conflict_ledger.state_path().read_text(encoding="utf-8")
    assert "C:\\Users\\kotov" not in raw
    assert "Traceback" not in raw
    assert "DROP_ME" not in raw
    assert "RAW_PAYLOAD_SHOULD_NOT_PERSIST" not in raw
    assert "SECRET_TOKEN_SHOULD_NOT_PERSIST" not in raw


def test_repeated_same_conflict_increments_repeat_count(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    first = conflict_ledger.record_conflict(
        source="test",
        action_id="llm.remote.call",
        policy_hit="oracle_window_closed",
        reason_code="DENY_ORACLE",
        args_digest="same",
    )
    second = conflict_ledger.record_conflict(
        source="test",
        action_id="llm.remote.call",
        policy_hit="oracle_window_closed",
        reason_code="DENY_ORACLE",
        args_digest="same",
    )

    assert second["conflict_id"] == first["conflict_id"]
    assert second["status"] == "repeated"
    assert second["repeat_count"] == 2
    state = json.loads(conflict_ledger.state_path().read_text(encoding="utf-8"))
    assert state["conflicts"][first["conflict_id"]]["repeat_count"] == 2


def test_different_action_or_policy_creates_separate_conflict(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    first = conflict_ledger.record_conflict(
        source="test",
        action_id="llm.remote.call",
        policy_hit="oracle_window_closed",
        reason_code="DENY_ORACLE",
        args_digest="same",
    )
    second = conflict_ledger.record_conflict(
        source="test",
        action_id="agent.queue.enqueue",
        policy_hit="ACTION_NOT_ALLOWED",
        reason_code="ACTION_NOT_ALLOWED",
        args_digest="same",
    )

    assert second["conflict_id"] != first["conflict_id"]
    state = json.loads(conflict_ledger.state_path().read_text(encoding="utf-8"))
    assert len(state["conflicts"]) == 2


def test_invalid_threshold_env_does_not_block_recording(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_CONFLICT_THRESHOLD", "not-an-int")

    row = conflict_ledger.record_conflict(
        source="test",
        action_id="local.search",
        policy_hit="DENY_NETWORK",
        reason_code="DENY_NETWORK",
        args_digest="threshold-digest",
    )

    assert row["conflict_id"].startswith("conflict_")
    assert row["threshold_candidate"] is False
