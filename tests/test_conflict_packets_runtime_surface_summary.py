# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from modules.volition import conflict_ledger, conflict_packets


def _record_owner_cooldown(args_digest: str = "same-owner-cooldown", **metadata):
    return conflict_ledger.record_conflict(
        source="dream",
        action_id="ask_owner",
        policy_hit="owner_prompt_cooldown",
        reason_code="ask_ivan_cooldown",
        reason="ASK_IVAN suppressed by cooldown.",
        intent_summary="Ask Ivan deferred by cooldown.",
        args_digest=args_digest,
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


def _exported_packet(conflict_id: str) -> dict:
    exported = conflict_packets.export_conflict_review_packet(conflict_id)
    assert exported["ok"] is True
    return exported["packet"]


def test_single_surface_packet_summary_counts_events_and_deduplicates_hook_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_CONFLICT_THRESHOLD", "2")

    first = _record_owner_cooldown(
        runtime_path="run_ester_fixed.dream_cycle",
        runtime_surface="run_ester",
        hook_id="ask_ivan_cooldown",
    )
    second = _record_owner_cooldown(
        runtime_path="run_ester_fixed.dream_cycle",
        runtime_surface="run_ester",
        hook_id="ask_ivan_cooldown",
    )

    assert second["conflict_id"] == first["conflict_id"]
    packet = _exported_packet(first["conflict_id"])
    summary = packet["runtime_surface_summary"]

    assert summary["event_count"] == 2
    assert summary["surface_count"] == 1
    assert summary["has_multiple_surfaces"] is False
    assert summary["surfaces"] == [
        {
            "runtime_path": "run_ester_fixed.dream_cycle",
            "runtime_surface": "run_ester",
            "hook_ids": ["ask_ivan_cooldown"],
            "count": 2,
        }
    ]


def test_multi_surface_packet_summary_preserves_semantic_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_CONFLICT_THRESHOLD", "2")

    first = _record_owner_cooldown(
        runtime_path="run_ester_fixed.dream_cycle",
        runtime_surface="run_ester",
        hook_id="ask_ivan_cooldown",
    )
    second = _record_owner_cooldown(
        runtime_path="telegram_bot.dream_cycle",
        runtime_surface="telegram_listener",
        hook_id="ask_ivan_cooldown",
    )

    assert second["conflict_id"] == first["conflict_id"]
    assert second["conflict_key"] == first["conflict_key"]
    assert second["repeat_count"] == 2
    packet = _exported_packet(first["conflict_id"])
    summary = packet["runtime_surface_summary"]

    assert packet["fingerprint"] == first["conflict_key"]
    assert packet["repeat_count"] == 2
    assert summary["event_count"] == 2
    assert summary["surface_count"] == 2
    assert summary["has_multiple_surfaces"] is True
    assert summary["surfaces"] == [
        {
            "runtime_path": "run_ester_fixed.dream_cycle",
            "runtime_surface": "run_ester",
            "hook_ids": ["ask_ivan_cooldown"],
            "count": 1,
        },
        {
            "runtime_path": "telegram_bot.dream_cycle",
            "runtime_surface": "telegram_listener",
            "hook_ids": ["ask_ivan_cooldown"],
            "count": 1,
        },
    ]


def test_packet_summary_excludes_raw_prompt_tokens_and_path_like_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_CONFLICT_THRESHOLD", "2")
    raw_path = r"C:\Users\kotov\secret\listener.py"

    _record_owner_cooldown(
        runtime_path="run_ester_fixed.dream_cycle",
        runtime_surface="run_ester",
        hook_id="ask_ivan_cooldown",
        prompt="RAW_PROMPT_SHOULD_NOT_PERSIST",
        token="SECRET_TOKEN_SHOULD_NOT_PERSIST",
    )
    second = _record_owner_cooldown(
        runtime_path=raw_path,
        runtime_surface="Traceback (most recent call last): File secret.py",
        hook_id="ask\nivan\tcooldown",
        full_payload="RAW_PAYLOAD_SHOULD_NOT_PERSIST",
    )

    packet = _exported_packet(second["conflict_id"])
    raw_packet = json.dumps(packet, ensure_ascii=False)

    assert "RAW_PROMPT_SHOULD_NOT_PERSIST" not in raw_packet
    assert "SECRET_TOKEN_SHOULD_NOT_PERSIST" not in raw_packet
    assert "RAW_PAYLOAD_SHOULD_NOT_PERSIST" not in raw_packet
    assert raw_path not in raw_packet
    assert "Traceback" not in raw_packet
    assert packet["runtime_surface_summary"]["event_count"] == 2
    assert packet["runtime_surface_summary"]["surfaces"] == [
        {
            "runtime_path": "run_ester_fixed.dream_cycle",
            "runtime_surface": "run_ester",
            "hook_ids": ["ask_ivan_cooldown"],
            "count": 1,
        },
    ]


def test_packet_remains_valid_without_runtime_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_CONFLICT_THRESHOLD", "2")

    first = _record_owner_cooldown(args_digest="no-runtime-identity")
    second = _record_owner_cooldown(args_digest="no-runtime-identity")

    packet = _exported_packet(first["conflict_id"])
    validation = conflict_packets.validate_review_packet(packet)

    assert second["conflict_id"] == first["conflict_id"]
    assert validation["ok"] is True
    assert packet["runtime_surface_summary"] == {
        "surfaces": [],
        "surface_count": 0,
        "event_count": 2,
        "has_multiple_surfaces": False,
    }
