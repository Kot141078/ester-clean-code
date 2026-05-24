# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from modules.thinking import action_registry
from modules.thinking.action_registry import invoke_guarded
from modules.volition import conflict_ledger, conflict_resolution
from modules.volition.volition_gate import VolitionContext, VolitionGate


def _make_conflict() -> dict:
    payload = {
        "source": "test",
        "action_id": "llm.remote.call",
        "policy_hit": "oracle_window_closed",
        "reason_code": "DENY_ORACLE",
        "reason": "oracle window closed",
        "slot": "A",
        "chain_id": "chain_resolution_test",
        "intent_summary": "remote oracle call for unsupported goal",
        "agent_id": "agent-resolution",
        "plan_id": "plan-resolution",
        "args_digest": "args-digest-resolution",
        "prompt_digest": "prompt-digest-resolution",
        "metadata": {"request_id": "request-resolution", "prompt": "RAW PROMPT", "api_key": "SECRET_TOKEN"},
    }
    conflict_ledger.record_conflict(**payload)
    conflict_ledger.record_conflict(**payload)
    return conflict_ledger.record_conflict(**payload)


def _valid_payload(**overrides) -> dict:
    payload = {
        "actor": "tester",
        "reframed_goal": {
            "reframed_action_id": "local.search",
            "reframed_intent_summary": "Use local indexed context instead of a remote oracle call.",
            "safety_delta": "Removes remote oracle/network dependency and stays inside local read-only review.",
        },
        "legitimacy_controls": {
            "budgets": ["max_actions=1", "read_only_review"],
            "windows": ["local_review_window"],
            "approvals": ["review_packet_present"],
            "constraints": ["no_network", "no_memory_write", "no_policy_change"],
            "gates": ["normal_volition_gate_required", "action_registry_required"],
        },
        "evidence_refs": ["conflict_packet:local"],
        "witness_refs": [],
        "scope": {
            "allowed_scope": "single local review artifact for this conflict",
            "single_action_only": True,
            "no_expiry_reason": "review artifact only; no runtime authorization",
        },
        "review_only": True,
        "does_not_authorize_original_action": True,
        "does_not_modify_policy": True,
        "does_not_authorize_future_similar_actions": True,
        "requires_normal_gate_execution": True,
        "notes": "safe summary only",
        "meta": {"reviewer": "pytest", "source": "unit", "review_id": "review-1"},
    }
    payload.update(overrides)
    return payload


def _network_ctx() -> VolitionContext:
    return VolitionContext(
        chain_id="chain_resolution_gate_test",
        step="action",
        actor="ester",
        intent="network probe after resolution",
        action_kind="network.probe",
        needs=["network"],
        budgets={"max_actions": 3, "max_work_ms": 2000},
        metadata={"action_id": "network.probe", "args_digest": "network-resolution-digest"},
    )


def test_valid_resolution_packet_can_be_created_for_existing_conflict(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    conflict = _make_conflict()

    rep = conflict_resolution.create_resolution_candidate(conflict["conflict_id"], _valid_payload())

    assert rep["ok"] is True
    assert rep["created"] is True
    assert rep["status"] == "evidence_reframed_allowed"
    loaded = conflict_resolution.get_resolution(conflict["conflict_id"])
    assert loaded["ok"] is True
    assert loaded["resolution"]["conflict_id"] == conflict["conflict_id"]
    assert loaded["resolution"]["review_only"] is True
    assert loaded["resolution"]["runtime_authorization"] is False
    assert loaded["resolution"]["creates_precedent"] is False
    assert loaded["resolution"]["validation_result"]["ok"] is True


def test_missing_original_policy_hit_is_invalid():
    rep = conflict_resolution.validate_resolution_packet(
        {
            "conflict_id": "conflict-a",
            "original_action_id": "local.search",
            "reframed_goal": {"safety_delta": "safe delta"},
            "legitimacy_controls": {"constraints": ["no_network"]},
            "review_only": True,
            "does_not_authorize_original_action": True,
            "does_not_modify_policy": True,
            "does_not_authorize_future_similar_actions": True,
            "requires_normal_gate_execution": True,
        }
    )

    assert rep["ok"] is False
    assert "original_policy_hit_required" in rep["errors"]


def test_missing_reframed_goal_is_invalid():
    rep = conflict_resolution.validate_resolution_packet(
        {
            "conflict_id": "conflict-a",
            "original_policy_hit": "DENY_NETWORK",
            "original_action_id": "local.search",
            "legitimacy_controls": {"constraints": ["no_network"]},
            "review_only": True,
            "does_not_authorize_original_action": True,
            "does_not_modify_policy": True,
            "does_not_authorize_future_similar_actions": True,
            "requires_normal_gate_execution": True,
        }
    )

    assert rep["ok"] is False
    assert "reframed_goal_required" in rep["errors"]


def test_missing_safety_delta_is_invalid():
    rep = conflict_resolution.validate_resolution_packet(
        {
            "conflict_id": "conflict-a",
            "original_policy_hit": "DENY_NETWORK",
            "original_action_id": "local.search",
            "reframed_goal": {"reframed_intent_summary": "local only"},
            "legitimacy_controls": {"constraints": ["no_network"]},
            "review_only": True,
            "does_not_authorize_original_action": True,
            "does_not_modify_policy": True,
            "does_not_authorize_future_similar_actions": True,
            "requires_normal_gate_execution": True,
        }
    )

    assert rep["ok"] is False
    assert "safety_delta_required" in rep["errors"]


def test_required_booleans_must_be_true():
    packet = {
        "conflict_id": "conflict-a",
        "original_policy_hit": "DENY_NETWORK",
        "original_action_id": "local.search",
        "reframed_goal": {"safety_delta": "safe delta"},
        "legitimacy_controls": {"constraints": ["no_network"]},
        "review_only": True,
        "does_not_authorize_original_action": False,
        "does_not_modify_policy": True,
        "does_not_authorize_future_similar_actions": True,
        "requires_normal_gate_execution": True,
    }

    rep = conflict_resolution.validate_resolution_packet(packet)

    assert rep["ok"] is False
    assert "required_non_authorization_flags_missing" in rep["errors"]


def test_review_only_must_be_true():
    packet = {
        "conflict_id": "conflict-a",
        "original_policy_hit": "DENY_NETWORK",
        "original_action_id": "local.search",
        "reframed_goal": {"safety_delta": "safe delta"},
        "legitimacy_controls": {"constraints": ["no_network"]},
        "review_only": False,
        "does_not_authorize_original_action": True,
        "does_not_modify_policy": True,
        "does_not_authorize_future_similar_actions": True,
        "requires_normal_gate_execution": True,
    }

    rep = conflict_resolution.validate_resolution_packet(packet)

    assert rep["ok"] is False
    assert "required_non_authorization_flags_missing" in rep["errors"]


def test_runtime_authorization_must_be_false():
    packet = {
        "conflict_id": "conflict-a",
        "original_policy_hit": "DENY_NETWORK",
        "original_action_id": "local.search",
        "reframed_goal": {"safety_delta": "safe delta"},
        "legitimacy_controls": {"constraints": ["no_network"]},
        "review_only": True,
        "runtime_authorization": True,
        "does_not_authorize_original_action": True,
        "does_not_modify_policy": True,
        "does_not_authorize_future_similar_actions": True,
        "requires_normal_gate_execution": True,
    }

    rep = conflict_resolution.validate_resolution_packet(packet)

    assert rep["ok"] is False
    assert "runtime_authorization_must_be_false" in rep["errors"]


def test_requires_normal_gate_execution_must_be_true():
    packet = {
        "conflict_id": "conflict-a",
        "original_policy_hit": "DENY_NETWORK",
        "original_action_id": "local.search",
        "reframed_goal": {"safety_delta": "safe delta"},
        "legitimacy_controls": {"constraints": ["no_network"]},
        "review_only": True,
        "does_not_authorize_original_action": True,
        "does_not_modify_policy": True,
        "does_not_authorize_future_similar_actions": True,
        "requires_normal_gate_execution": False,
    }

    rep = conflict_resolution.validate_resolution_packet(packet)

    assert rep["ok"] is False
    assert "normal_gate_execution_required" in rep["errors"]


def test_oracle_window_conflict_without_window_or_approval_controls_is_invalid(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    conflict = _make_conflict()

    rep = conflict_resolution.create_resolution_candidate(
        conflict["conflict_id"],
        _valid_payload(legitimacy_controls={"constraints": ["no_network"]}),
    )

    assert rep["ok"] is False
    assert rep["status"] == "policy_review"
    assert "oracle_controls_required" in rep["validation_result"]["errors"]
    assert "window_controls_required" in rep["validation_result"]["errors"]


def test_valid_resolution_sets_conflict_status_to_evidence_reframed_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    conflict = _make_conflict()

    rep = conflict_resolution.create_resolution_candidate(conflict["conflict_id"], _valid_payload())

    assert rep["ok"] is True
    state = conflict_ledger.state_path().read_text(encoding="utf-8")
    assert "evidence_reframed_allowed" in state
    assert rep["resolution_id"] in state
    assert '"review_only": true' in state
    assert '"runtime_authorization": false' in state
    assert '"normal_gate_required": true' in state
    assert '"creates_precedent": false' in state


def test_invalid_resolution_cannot_set_evidence_reframed_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    conflict = _make_conflict()

    rep = conflict_resolution.create_resolution_candidate(
        conflict["conflict_id"],
        _valid_payload(reframed_goal={"reframed_intent_summary": "missing safety delta"}),
    )

    assert rep["ok"] is False
    state = conflict_ledger.state_path().read_text(encoding="utf-8")
    assert "policy_review" in state
    assert "evidence_reframed_allowed" not in state


def test_resolution_does_not_change_gate_or_action_registry_deny_behavior(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_SLOT", "B")
    monkeypatch.setenv("ESTER_ALLOW_NETWORK", "0")
    monkeypatch.setenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")
    conflict = _make_conflict()
    created = conflict_resolution.create_resolution_candidate(conflict["conflict_id"], _valid_payload())
    assert created["ok"] is True

    rep = invoke_guarded("network.probe", {}, ctx=_network_ctx(), gate=VolitionGate())

    assert rep["ok"] is False
    assert rep["error"] == "volition_denied"
    assert rep["reason_code"] == "DENY_NETWORK"


def test_resolution_does_not_make_action_registry_allow_oracle_call(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_SLOT", "A")
    monkeypatch.setenv("ESTER_ALLOW_NETWORK", "0")
    monkeypatch.setenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")
    conflict = _make_conflict()
    created = conflict_resolution.create_resolution_candidate(conflict["conflict_id"], _valid_payload())
    assert created["ok"] is True

    rep = action_registry.invoke(
        "llm.remote.call",
        {"prompt": "raw prompt stays in test process", "purpose": "resolution safety test", "max_tokens": 8},
    )

    assert rep["ok"] is False
    assert rep["error"] == "oracle_window_closed"


def test_raw_prompt_secret_and_full_args_are_not_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    conflict = _make_conflict()
    payload = _valid_payload(
        raw_prompt="RAW_PROMPT_SHOULD_NOT_APPEAR",
        api_key="SECRET_TOKEN",
        full_args={"token": "SECRET_TOKEN", "prompt": "RAW_PROMPT_SHOULD_NOT_APPEAR"},
        meta={"reviewer": "pytest", "api_key": "SECRET_TOKEN", "source": "unit"},
    )

    rep = conflict_resolution.create_resolution_candidate(conflict["conflict_id"], payload)

    assert rep["ok"] is True
    raw = Path(rep["resolution_path"]).read_text(encoding="utf-8")
    raw += conflict_ledger.state_path().read_text(encoding="utf-8")
    assert "RAW_PROMPT_SHOULD_NOT_APPEAR" not in raw
    assert "SECRET_TOKEN" not in raw
    assert "full_args" not in raw


def test_storage_failure_fails_closed_without_status_change(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    conflict = _make_conflict()

    def boom(_path, _packet):
        raise OSError("storage down")

    monkeypatch.setattr(conflict_resolution, "_write_resolution", boom)
    rep = conflict_resolution.create_resolution_candidate(conflict["conflict_id"], _valid_payload())

    assert rep["ok"] is False
    assert rep["created"] is False
    assert rep["error"] == "resolution_storage_failed"
    state = conflict_ledger.state_path().read_text(encoding="utf-8")
    assert "evidence_reframed_allowed" not in state
