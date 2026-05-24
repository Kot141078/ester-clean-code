# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from modules.volition import conflict_ledger, conflict_packets


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _record_owner_cooldown(**metadata):
    return conflict_ledger.record_conflict(
        source="dream",
        action_id="ask_owner",
        policy_hit="owner_prompt_cooldown",
        reason_code="ask_ivan_cooldown",
        reason="ASK_IVAN suppressed by cooldown.",
        intent_summary="Ask Ivan deferred by cooldown.",
        args_digest="same-owner-cooldown",
        metadata={
            "runtime_authorization": False,
            "does_not_modify_policy": True,
            "does_not_authorize_action": True,
            "does_not_delete_signal": True,
            "does_not_suppress_review": True,
            "suppressed": True,
            "cooldown_active": True,
            **metadata,
        },
    )


def test_same_semantic_conflict_groups_and_jsonl_preserves_runtime_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_CONFLICT_THRESHOLD", "2")

    first = _record_owner_cooldown(
        runtime_path="run_ester_fixed.dream_cycle",
        hook_id="ask_ivan_cooldown",
        runtime_surface="run_ester",
        hook_family="dream_conflict_bridge",
    )
    second = _record_owner_cooldown(
        runtime_path="telegram_bot.dream_cycle",
        hook_id="ask_ivan_cooldown",
        runtime_surface="telegram_listener",
        hook_family="dream_conflict_bridge",
    )

    assert second["conflict_id"] == first["conflict_id"]
    assert second["conflict_key"] == first["conflict_key"]
    assert second["repeat_count"] == 2

    rows = _read_jsonl(conflict_ledger.conflicts_path())
    assert [row["metadata"]["runtime_path"] for row in rows] == [
        "run_ester_fixed.dream_cycle",
        "telegram_bot.dream_cycle",
    ]
    assert [row["metadata"]["hook_id"] for row in rows] == [
        "ask_ivan_cooldown",
        "ask_ivan_cooldown",
    ]

    state = json.loads(conflict_ledger.state_path().read_text(encoding="utf-8"))
    conflict_state = state["conflicts"][first["conflict_id"]]
    assert conflict_state["repeat_count"] == 2
    assert conflict_state["source"] == "dream"
    assert conflict_state["sources"] == ["dream"]
    assert "runtime_path" not in conflict_state
    assert "hook_id" not in conflict_state
    assert "runtime_surface" not in conflict_state
    assert "hook_family" not in conflict_state

    assert second["review_packet"]["ok"] is True
    assert second["review_packet"]["created"] is True
    exported = conflict_packets.export_conflict_review_packet(first["conflict_id"])
    assert exported["ok"] is True
    packet = exported["packet"]
    assert packet["repeat_count"] == 2
    assert packet["sources"] == ["dream"]
    assert "runtime_path" not in packet
    assert "hook_id" not in packet
    assert "runtime_surface" not in packet
    assert "hook_family" not in packet


def test_runtime_identity_rejects_local_paths_without_changing_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    first = _record_owner_cooldown(
        runtime_path="run_ester_fixed.dream_cycle",
        hook_id="ask_ivan_cooldown",
    )
    second = _record_owner_cooldown(
        runtime_path=r"C:\Users\kotov\secret\listener.py",
        hook_id="ask\nivan\tcooldown",
        runtime_surface="run_ester",
        hook_family="dream_conflict_bridge",
    )

    assert second["conflict_id"] == first["conflict_id"]
    assert second["conflict_key"] == first["conflict_key"]
    assert second["repeat_count"] == 2
    assert "runtime_path" not in second["metadata"]
    assert second["metadata"]["hook_id"] == "ask ivan cooldown"

    raw = conflict_ledger.conflicts_path().read_text(encoding="utf-8")
    raw += conflict_ledger.state_path().read_text(encoding="utf-8")
    assert r"C:\Users\kotov\secret\listener.py" not in raw
