# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from modules.thinking.action_registry import invoke_guarded
from modules.volition import attention_rebalancer, conflict_ledger
from modules.volition.volition_gate import VolitionContext, VolitionGate


def _record_conflict(**overrides):
    payload = {
        "source": "dream",
        "action_id": "self_search",
        "policy_hit": "self_search_throttle",
        "reason_code": "self_search_throttle",
        "reason": "self search throttled",
        "intent_summary": "safe summary",
        "args_digest": "attention-digest",
        "metadata": {"severity": "low", "signal_digest": "signal-digest", "summary_digest": "summary-digest"},
    }
    payload.update(overrides)
    return conflict_ledger.record_conflict(**payload)


def _repeat_conflict(times: int = 1, **overrides):
    row = {}
    for _ in range(times):
        row = _record_conflict(**overrides)
    return row


def _state() -> dict:
    return json.loads(conflict_ledger.state_path().read_text(encoding="utf-8"))


def _set_conflict_status(conflict_id: str, status: str, **extra) -> None:
    state = _state()
    conflict = dict(state["conflicts"][conflict_id])
    conflict["status"] = status
    conflict.update(extra)
    state["conflicts"][conflict_id] = conflict
    conflict_ledger.state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _network_ctx() -> VolitionContext:
    return VolitionContext(
        chain_id="chain_attention_test",
        step="action",
        actor="ester",
        intent="network probe after advisory",
        action_kind="network.probe",
        needs=["network"],
        budgets={"max_actions": 3, "max_work_ms": 2000},
        metadata={"action_id": "network.probe", "args_digest": "attention-network-digest"},
    )


def test_below_threshold_low_severity_creates_no_recommendation(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    row = _repeat_conflict(1)

    rep = attention_rebalancer.maybe_create_rebalance_recommendation(row["conflict_id"])

    assert rep["ok"] is True
    assert rep["created"] is False
    assert rep["reason"] == "below_threshold"
    assert attention_rebalancer.list_rebalance_recommendations() == []


def test_repeat_count_at_threshold_creates_recommendation(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    row = _repeat_conflict(5)

    rep = attention_rebalancer.maybe_create_rebalance_recommendation(row["conflict_id"])

    assert rep["ok"] is True
    assert rep["created"] is True
    rec = rep["recommendation"]
    assert rec["trigger"]["reason"] == "repeat_threshold"
    assert rec["trigger"]["repeat_count"] == 5
    assert rec["action"]["lower_salience"] is True
    assert rec["action"]["cooldown_recommended"] is True


def test_high_severity_creates_recommendation_below_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    row = _repeat_conflict(1, metadata={"severity": "high", "signal_digest": "signal-digest"})

    rep = attention_rebalancer.maybe_create_rebalance_recommendation(row["conflict_id"])

    assert rep["ok"] is True
    assert rep["created"] is True
    rec = rep["recommendation"]
    assert rec["trigger"]["reason"] == "high_severity"
    assert rec["trigger"]["severity"] == "high"
    assert rec["action"]["defocus"] is True


def test_evidence_reframed_allowed_is_monitor_only_without_defocus(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    row = _repeat_conflict(1)
    _set_conflict_status(row["conflict_id"], "evidence_reframed_allowed", last_resolution_id="resolution-a")

    rep = attention_rebalancer.maybe_create_rebalance_recommendation(row["conflict_id"])

    assert rep["ok"] is True
    rec = rep["recommendation"]
    assert rec["source_status"] == "evidence_reframed_allowed"
    assert rec["trigger"]["reason"] == "evidence_reframed_allowed_monitor_only"
    assert rec["action"]["defocus"] is False
    assert rec["action"]["lower_salience"] is False
    assert rec["suggested_cooldown_sec"] == 0
    assert rec["suggested_salience_multiplier"] == 1.0
    assert rec["review_refs"]["resolution_id"] == "resolution-a"
    assert rec["safety_flags"]["does_not_authorize_action"] is True
    assert rec["safety_flags"]["requires_future_runtime_hook"] is True


def test_policy_review_creates_mild_advisory_defocus(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    row = _repeat_conflict(1)
    _set_conflict_status(row["conflict_id"], "policy_review")

    rep = attention_rebalancer.maybe_create_rebalance_recommendation(row["conflict_id"])

    assert rep["ok"] is True
    rec = rep["recommendation"]
    assert rec["trigger"]["reason"] == "policy_review"
    assert rec["action"]["lower_salience"] is True
    assert rec["action"]["defocus"] is False
    assert rec["action"]["cooldown_recommended"] is True
    assert rec["safety_flags"]["does_not_suppress_review"] is True
    assert rec["safety_flags"]["does_not_delete_conflict"] is True


def test_denied_final_creates_stronger_defocus_recommendation(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    row = _repeat_conflict(1)
    _set_conflict_status(row["conflict_id"], "denied_final")

    rep = attention_rebalancer.maybe_create_rebalance_recommendation(row["conflict_id"])

    assert rep["ok"] is True
    rec = rep["recommendation"]
    assert rec["trigger"]["reason"] == "denied_final"
    assert rec["action"] == {
        "lower_salience": True,
        "defocus": True,
        "cooldown_recommended": True,
        "redirect_to_allowed_tasks": True,
    }
    assert rec["suggested_salience_multiplier"] == 0.25
    assert rec["suggested_cooldown_sec"] == 86400


def test_recommendation_safety_flags_are_all_true(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    row = _repeat_conflict(5)

    rec = attention_rebalancer.maybe_create_rebalance_recommendation(row["conflict_id"])["recommendation"]

    assert rec["safety_flags"] == {
        "advisory_only": True,
        "does_not_modify_policy": True,
        "does_not_authorize_action": True,
        "does_not_delete_conflict": True,
        "does_not_suppress_review": True,
        "requires_future_runtime_hook": True,
    }


def test_recommendation_does_not_modify_conflict_state(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    row = _repeat_conflict(5)
    before = conflict_ledger.state_path().read_text(encoding="utf-8")

    rep = attention_rebalancer.maybe_create_rebalance_recommendation(row["conflict_id"])

    assert rep["created"] is True
    after = conflict_ledger.state_path().read_text(encoding="utf-8")
    assert after == before


def test_recommendation_does_not_authorize_runtime_action(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_SLOT", "B")
    monkeypatch.setenv("ESTER_ALLOW_NETWORK", "0")
    monkeypatch.setenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")
    row = _repeat_conflict(5)
    rec = attention_rebalancer.maybe_create_rebalance_recommendation(row["conflict_id"])["recommendation"]

    rep = invoke_guarded("network.probe", {}, ctx=_network_ctx(), gate=VolitionGate())

    assert rec["safety_flags"]["does_not_authorize_action"] is True
    assert rep["ok"] is False
    assert rep["error"] == "volition_denied"
    assert rep["reason_code"] == "DENY_NETWORK"


def test_raw_dream_prompt_secret_and_full_args_are_not_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    row = _repeat_conflict(
        5,
        reason_code="",
        reason="RAW_DREAM_TEXT_SHOULD_NOT_APPEAR",
        intent_summary="RAW_PROMPT_SHOULD_NOT_APPEAR",
        metadata={
            "severity": "high",
            "api_key": "SECRET_TOKEN_SHOULD_NOT_APPEAR",
            "prompt": "RAW_PROMPT_SHOULD_NOT_APPEAR",
            "signal_digest": "signal-digest",
        },
    )

    rep = attention_rebalancer.maybe_create_rebalance_recommendation(row["conflict_id"])

    raw = Path(rep["recommendation_path"]).read_text(encoding="utf-8")
    assert "RAW_DREAM_TEXT_SHOULD_NOT_APPEAR" not in raw
    assert "RAW_PROMPT_SHOULD_NOT_APPEAR" not in raw
    assert "SECRET_TOKEN_SHOULD_NOT_APPEAR" not in raw
    assert "full_args" not in raw


def test_storage_failure_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    row = _repeat_conflict(5)

    def boom(_path, _payload):
        raise OSError("disk unavailable")

    monkeypatch.setattr(attention_rebalancer, "_write_json", boom)

    rep = attention_rebalancer.maybe_create_rebalance_recommendation(row["conflict_id"])

    assert rep["ok"] is False
    assert rep["created"] is False
    assert rep["error"] == "recommendation_storage_failed"
    assert attention_rebalancer.list_rebalance_recommendations() == []
