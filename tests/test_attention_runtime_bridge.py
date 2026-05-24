# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from modules.thinking import affect_reflection
from modules.volition import attention_rebalancer, attention_runtime_bridge, conflict_ledger


def _clear_flags(monkeypatch):
    for name in (
        "ESTER_ATTENTION_REBALANCE_ENABLE",
        "ESTER_ATTENTION_REBALANCE_DRY_RUN",
        "ESTER_ATTENTION_REBALANCE_APPLY_DREAM",
        "ESTER_ATTENTION_REBALANCE_APPLY_REFLECTION",
    ):
        monkeypatch.delenv(name, raising=False)


def _record_conflict(tmp_path, monkeypatch, status: str = "denied_final") -> dict:
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    row = conflict_ledger.record_conflict(
        source="dream",
        action_id="self_search",
        policy_hit="self_search_throttle",
        reason_code="self_search_throttle",
        reason="self search throttled",
        intent_summary="safe summary",
        args_digest="attention-runtime-digest",
        metadata={
            "severity": "low",
            "signal_type": "hypothesis",
            "signal_digest": "signal-digest",
            "summary_digest": "summary-digest",
            "policy_hit": "self_search_throttle",
        },
    )
    state = json.loads(conflict_ledger.state_path().read_text(encoding="utf-8"))
    conflict = dict(state["conflicts"][row["conflict_id"]])
    conflict["status"] = status
    state["conflicts"][row["conflict_id"]] = conflict
    conflict_ledger.state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rep = attention_rebalancer.maybe_create_rebalance_recommendation(row["conflict_id"])
    assert rep["ok"] is True
    assert rep["created"] is True
    rec = dict(rep["recommendation"])
    rec["recommendation_path"] = rep["recommendation_path"]
    return rec


def _bias(**overrides):
    payload = {
        "source": "dream",
        "signal_type": "hypothesis",
        "proposed_action": "self_search",
        "policy_hit": "self_search_throttle",
        "digest": "signal-digest",
        "summary": "",
        "meta": {"signal_digest": "signal-digest", "summary_digest": "summary-digest"},
    }
    payload.update(overrides)
    return attention_runtime_bridge.get_runtime_attention_bias(**payload)


def _reflection_item(now: float = 1000.0) -> dict:
    return {
        "text": "reflection candidate",
        "meta": {
            "ts": now,
            "importance": 0.8,
            "affect": {"valence": 0.1, "arousal": 0.7},
            "signal_type": "reflection_signal",
            "action_id": "self_search",
            "policy_hit": "self_search_throttle",
            "signal_digest": "signal-digest",
            "summary_digest": "summary-digest",
        },
    }


def test_enable_default_off_preserves_behavior(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_conflict(tmp_path, monkeypatch, "denied_final")

    rep = _bias()

    assert rep["enabled"] is False
    assert rep["matched"] is False
    assert rep["salience_multiplier"] == 1.0
    assert rep["defocus"] is False


def test_dry_run_reports_would_apply_without_changing_salience(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_conflict(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    rep = _bias()

    assert rep["enabled"] is True
    assert rep["dry_run"] is True
    assert rep["matched"] is True
    assert rep["reason"] == "dry_run"
    assert rep["would_apply"] is True
    assert rep["would_salience_multiplier"] < 1.0
    assert rep["salience_multiplier"] == 1.0
    assert rep["defocus"] is False


def test_apply_flags_off_preserve_behavior(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_conflict(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")

    rep = _bias()

    assert rep["matched"] is True
    assert rep["reason"] == "apply_flag_disabled"
    assert rep["apply_allowed"] is False
    assert rep["salience_multiplier"] == 1.0
    assert rep["defocus"] is False


def test_apply_dream_denied_final_reduces_salience(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_conflict(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    rep = _bias()

    assert rep["apply_allowed"] is True
    assert 0.05 <= rep["salience_multiplier"] < 1.0
    assert rep["defocus"] is True


def test_policy_review_uses_milder_multiplier_than_denied_final(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_conflict(tmp_path / "denied", monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")
    denied = _bias()

    _record_conflict(tmp_path / "review", monkeypatch, "policy_review")
    review = _bias()

    assert denied["salience_multiplier"] < review["salience_multiplier"] < 1.0
    assert review["defocus"] is False


def test_evidence_reframed_allowed_monitor_only_does_not_reduce_salience(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_conflict(tmp_path, monkeypatch, "evidence_reframed_allowed")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    rep = _bias()

    assert rep["matched"] is True
    assert rep["reason"] == "monitor_only"
    assert rep["salience_multiplier"] == 1.0
    assert rep["defocus"] is False


def test_runtime_authorization_is_always_false(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_conflict(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    assert _bias()["runtime_authorization"] is False
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "1")
    assert _bias()["runtime_authorization"] is False
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "0")
    assert _bias()["runtime_authorization"] is False


def test_signal_is_never_deleted_or_suppressed(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_conflict(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    rep = _bias()

    assert rep["does_not_delete_signal"] is True
    assert rep["does_not_suppress_review"] is True
    assert rep["does_not_modify_policy"] is True


def test_raw_prompt_secret_and_full_args_are_not_persisted_or_returned(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    rec = _record_conflict(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "1")

    rep = _bias(
        summary="RAW_PROMPT_SHOULD_NOT_APPEAR",
        meta={
            "signal_digest": "signal-digest",
            "summary_digest": "summary-digest",
            "prompt": "RAW_PROMPT_SHOULD_NOT_APPEAR",
            "api_key": "SECRET_TOKEN_SHOULD_NOT_APPEAR",
            "full_args": "FULL_ARGS_SHOULD_NOT_APPEAR",
        },
    )

    raw_return = json.dumps(rep, ensure_ascii=False, sort_keys=True)
    assert "RAW_PROMPT_SHOULD_NOT_APPEAR" not in raw_return
    assert "SECRET_TOKEN_SHOULD_NOT_APPEAR" not in raw_return
    assert "FULL_ARGS_SHOULD_NOT_APPEAR" not in raw_return
    raw_file = Path(rec["recommendation_path"]).read_text(encoding="utf-8")
    assert "RAW_PROMPT_SHOULD_NOT_APPEAR" not in raw_file
    assert "SECRET_TOKEN_SHOULD_NOT_APPEAR" not in raw_file
    assert "FULL_ARGS_SHOULD_NOT_APPEAR" not in raw_file


def test_reflection_score_preserved_by_default_and_reduced_only_when_explicitly_enabled(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    monkeypatch.setattr(affect_reflection.time, "time", lambda: 1000.0)
    _record_conflict(tmp_path, monkeypatch, "denied_final")
    item = _reflection_item()

    default_score = affect_reflection.score_item(item)
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_REFLECTION", "1")
    dry_score = affect_reflection.score_item(item)
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    apply_score = affect_reflection.score_item(item)

    assert dry_score == default_score
    assert 0.0 <= apply_score < default_score


def test_reflection_score_unchanged_when_enable_is_zero(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    monkeypatch.setattr(affect_reflection.time, "time", lambda: 1000.0)
    _record_conflict(tmp_path, monkeypatch, "denied_final")
    item = _reflection_item()

    default_score = affect_reflection.score_item(item)
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_REFLECTION", "1")

    assert affect_reflection.score_item(item) == default_score


def test_reflection_score_unchanged_when_apply_reflection_is_off(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    monkeypatch.setattr(affect_reflection.time, "time", lambda: 1000.0)
    _record_conflict(tmp_path, monkeypatch, "denied_final")
    item = _reflection_item()

    default_score = affect_reflection.score_item(item)
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_REFLECTION", "0")

    assert affect_reflection.score_item(item) == default_score


def test_reflection_bridge_failure_preserves_original_score(monkeypatch):
    _clear_flags(monkeypatch)
    monkeypatch.setattr(affect_reflection.time, "time", lambda: 1000.0)
    item = _reflection_item()
    default_score = affect_reflection.score_item(item)

    def boom(**_kwargs):
        raise RuntimeError("bridge unavailable")

    monkeypatch.setattr(attention_runtime_bridge, "get_runtime_attention_bias", boom)
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_REFLECTION", "1")

    assert affect_reflection.score_item(item) == default_score


def test_reflection_candidate_is_queued_not_deleted_when_reduced(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    monkeypatch.setattr(affect_reflection.time, "time", lambda: 1000.0)
    _record_conflict(tmp_path, monkeypatch, "denied_final")
    affect_reflection._heap.clear()
    item = _reflection_item()
    default_score = affect_reflection.score_item(item)
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_REFLECTION", "1")

    rep = affect_reflection.enqueue(item)

    assert rep["ok"] is True
    assert rep["size"] == 1
    assert 0.0 <= rep["score"] < default_score
    assert affect_reflection._heap[0][1]["text"] == "reflection candidate"
