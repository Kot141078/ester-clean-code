# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from modules.dreams import dream_candidate_scoring
from modules.volition import attention_rebalancer, conflict_ledger


def _clear_flags(monkeypatch):
    for name in (
        "ESTER_ATTENTION_REBALANCE_ENABLE",
        "ESTER_ATTENTION_REBALANCE_DRY_RUN",
        "ESTER_ATTENTION_REBALANCE_APPLY_DREAM",
        "ESTER_ATTENTION_REBALANCE_APPLY_REFLECTION",
    ):
        monkeypatch.delenv(name, raising=False)


def _record_recommendation(tmp_path, monkeypatch, status: str = "denied_final") -> dict:
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    row = conflict_ledger.record_conflict(
        source="dream",
        action_id="self_search",
        policy_hit="self_search_throttle",
        reason_code="self_search_throttle",
        reason="self search throttled",
        intent_summary="safe summary",
        args_digest="dream-candidate-score-digest",
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


def _candidate(**overrides):
    payload = {
        "id": "candidate-1",
        "title": "safe title",
        "summary": "safe summary",
        "proposed_action": "self_search",
        "policy_hit": "self_search_throttle",
        "reason_code": "self_search_throttle",
        "digest": "signal-digest",
        "meta": {"signal_digest": "signal-digest", "summary_digest": "summary-digest"},
    }
    payload.update(overrides)
    return payload


def _score(**overrides):
    payload = {
        "candidate": _candidate(),
        "base_score": 1.0,
        "source": "dream",
        "signal_type": "hypothesis",
        "apply_runtime_bias": True,
    }
    payload.update(overrides)
    return dream_candidate_scoring.score_dream_candidate(**payload)


def test_default_env_score_unchanged(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_recommendation(tmp_path, monkeypatch, "denied_final")

    rep = _score()

    assert rep["enabled"] is False
    assert rep["score"] == 1.0
    assert rep["changed"] is False
    assert rep["runtime_authorization"] is False


def test_enable_zero_score_unchanged(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_recommendation(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    rep = _score()

    assert rep["enabled"] is False
    assert rep["score"] == 1.0
    assert rep["changed"] is False


def test_dry_run_score_unchanged_with_would_apply_metadata(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_recommendation(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    rep = _score()

    assert rep["matched"] is True
    assert rep["dry_run"] is True
    assert rep["score"] == 1.0
    assert rep["changed"] is False
    assert rep["would_multiplier"] < 1.0
    assert rep["would_score"] < 1.0


def test_apply_dream_off_score_unchanged(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_recommendation(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "0")

    rep = _score()

    assert rep["matched"] is True
    assert rep["bridge_apply_allowed"] is False
    assert rep["score"] == 1.0
    assert rep["changed"] is False


def test_apply_dream_denied_final_reduces_score(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_recommendation(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    rep = _score()

    assert rep["apply_allowed"] is True
    assert rep["changed"] is True
    assert 0.05 <= rep["score"] < 1.0
    assert 0.05 <= rep["multiplier"] < 1.0


def test_policy_review_reduction_is_milder_than_denied_final(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_recommendation(tmp_path / "denied", monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")
    denied = _score()

    _record_recommendation(tmp_path / "review", monkeypatch, "policy_review")
    review = _score()

    assert 0.05 <= denied["score"] < review["score"] < 1.0
    assert denied["multiplier"] < review["multiplier"] < 1.0


def test_evidence_reframed_monitor_only_keeps_score(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_recommendation(tmp_path, monkeypatch, "evidence_reframed_allowed")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    rep = _score()

    assert rep["matched"] is True
    assert rep["score"] == 1.0
    assert rep["multiplier"] == 1.0
    assert rep["changed"] is False


def test_candidate_is_never_deleted_or_suppressed(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_recommendation(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    rep = _score()

    assert rep["does_not_delete_signal"] is True
    assert rep["does_not_suppress_review"] is True
    assert rep["does_not_modify_policy"] is True


def test_runtime_authorization_always_false(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_recommendation(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    assert _score()["runtime_authorization"] is False
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "1")
    assert _score()["runtime_authorization"] is False
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "0")
    assert _score()["runtime_authorization"] is False


def test_raw_dream_prompt_secret_full_args_are_not_persisted_or_returned(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    rec = _record_recommendation(tmp_path, monkeypatch, "denied_final")
    before = {str(p) for p in Path(tmp_path).rglob("*") if p.is_file()}
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "1")
    raw_candidate = _candidate(
        text="RAW_DREAM_TEXT_SHOULD_NOT_APPEAR",
        summary="RAW_PROMPT_SHOULD_NOT_APPEAR",
        full_args="FULL_ARGS_SHOULD_NOT_APPEAR",
        meta={
            "signal_digest": "signal-digest",
            "summary_digest": "summary-digest",
            "api_key": "SECRET_TOKEN_SHOULD_NOT_APPEAR",
            "prompt": "RAW_PROMPT_SHOULD_NOT_APPEAR",
        },
    )

    rep = _score(candidate=raw_candidate)

    raw_return = json.dumps(rep, ensure_ascii=False, sort_keys=True)
    assert "RAW_DREAM_TEXT_SHOULD_NOT_APPEAR" not in raw_return
    assert "RAW_PROMPT_SHOULD_NOT_APPEAR" not in raw_return
    assert "FULL_ARGS_SHOULD_NOT_APPEAR" not in raw_return
    assert "SECRET_TOKEN_SHOULD_NOT_APPEAR" not in raw_return
    raw_file = Path(rec["recommendation_path"]).read_text(encoding="utf-8")
    assert "RAW_DREAM_TEXT_SHOULD_NOT_APPEAR" not in raw_file
    assert "RAW_PROMPT_SHOULD_NOT_APPEAR" not in raw_file
    assert "FULL_ARGS_SHOULD_NOT_APPEAR" not in raw_file
    assert "SECRET_TOKEN_SHOULD_NOT_APPEAR" not in raw_file
    after = {str(p) for p in Path(tmp_path).rglob("*") if p.is_file()}
    assert after == before


def test_bridge_failure_returns_original_score(monkeypatch):
    _clear_flags(monkeypatch)

    def boom(*_args, **_kwargs):
        raise RuntimeError("bridge unavailable")

    monkeypatch.setattr(
        "modules.volition.attention_runtime_bridge.get_runtime_attention_bias",
        boom,
    )
    rep = _score(candidate=_candidate(text="RAW_DREAM_TEXT_SHOULD_NOT_APPEAR"), base_score=0.7)

    assert rep["reason"] == "attention_bridge_failed"
    assert rep["score"] == 0.7
    assert rep["changed"] is False
    assert rep["runtime_authorization"] is False


def test_scaffold_default_does_not_apply_even_when_bridge_allows(tmp_path, monkeypatch):
    _clear_flags(monkeypatch)
    _record_recommendation(tmp_path, monkeypatch, "denied_final")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_ENABLE", "1")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_DRY_RUN", "0")
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    rep = dream_candidate_scoring.score_dream_candidate(candidate=_candidate(), base_score=1.0)

    assert rep["bridge_apply_allowed"] is True
    assert rep["runtime_bias_requested"] is False
    assert rep["score"] == 1.0
    assert rep["changed"] is False
