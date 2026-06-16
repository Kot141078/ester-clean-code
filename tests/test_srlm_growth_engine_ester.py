# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from flask import Flask

from growth_engine_ester.config import load_config
from growth_engine_ester.decision_adapter import shadow_step
from growth_engine_ester.policy import validate_params
from growth_engine_ester.promotion_adapter import promote_candidate, rollback, verify_witness
from growth_engine_ester.reports import build_report
from growth_engine_ester.routes import register as register_srlm_routes
from growth_engine_ester.signals import record_outcome
from growth_engine_ester.state import load_promoted_policy, write_promoted_policy


def _clear_env(monkeypatch, root: Path) -> None:
    for key in (
        "ESTER_SRLM_ENABLE",
        "ESTER_SRLM_ACK_RISK",
        "ESTER_SRLM_ALLOW_PROMOTE",
        "ESTER_SRLM_SHADOW_ONLY",
        "ESTER_SRLM_CANARY_ENABLE",
        "ESTER_SRLM_PROMOTE_LOW_ONLY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ESTER_SRLM_ROOT", str(root))


def _enable_promotion(monkeypatch, root: Path) -> None:
    _clear_env(monkeypatch, root)
    monkeypatch.setenv("ESTER_SRLM_ENABLE", "1")
    monkeypatch.setenv("ESTER_SRLM_ACK_RISK", "I_UNDERSTAND")
    monkeypatch.setenv("ESTER_SRLM_ALLOW_PROMOTE", "1")
    monkeypatch.setenv("ESTER_SRLM_SHADOW_ONLY", "0")
    monkeypatch.setenv("ESTER_SRLM_MIN_MARGIN", "0.001")
    monkeypatch.setenv("ESTER_SRLM_MAX_PROMOTIONS_PER_WINDOW", "10")


def _current_params() -> dict[str, float]:
    return {
        "router.local_weight": 0.0,
        "router.judge_weight": 0.0,
        "router.online_weight": 0.0,
        "retrieval.semantic_weight": 0.0,
        "retrieval.structured_weight": 0.0,
        "retrieval.card_weight": 0.0,
        "memory.salience_threshold": 0.0,
        "reflection.cooldown_sec": 0.0,
        "dream.priority_bias": 0.0,
        "conflict.defocus_threshold": 0.0,
        "answer.max_context_items": 0.0,
        "tool.timeout_soft_sec": 0.0,
    }


def _better_params() -> dict[str, float]:
    params = _current_params()
    params.update(
        {
            "router.local_weight": 0.8,
            "router.judge_weight": 0.7,
            "router.online_weight": 0.5,
            "retrieval.semantic_weight": 0.8,
            "answer.max_context_items": 4.0,
        }
    )
    return params


def test_srlm_disabled_by_default(tmp_path, monkeypatch):
    _clear_env(monkeypatch, tmp_path)
    cfg = load_config()
    assert cfg.enable is False
    assert cfg.shadow_only is True
    assert cfg.promotion_gate_open is False


def test_invalid_fitness_source_and_model_self_score_rejected(tmp_path, monkeypatch):
    _clear_env(monkeypatch, tmp_path)
    bad = record_outcome({"episode_id": "e1", "score": 0.5, "source": "judge"}, root=str(tmp_path))
    model = record_outcome({"episode_id": "e2", "score": 0.5, "source": "model"}, root=str(tmp_path))
    assert bad["ok"] is False and bad["error_code"] == "FITNESS_SOURCE_INVALID"
    assert model["ok"] is False and model["error_code"] == "FITNESS_SOURCE_INVALID"


def test_blocked_params_rejected():
    rep = validate_params({"identity.core_name": 1.0})
    assert rep["ok"] is False
    assert rep["error_code"] == "SRLM_PARAM_BLOCKED"


def test_shadow_run_has_no_state_side_effects(tmp_path, monkeypatch):
    _clear_env(monkeypatch, tmp_path)
    rep = shadow_step({"current_params": _current_params(), "proposed_params": _better_params()}, root=str(tmp_path))
    assert rep["ok"] is True
    assert rep["eval"]["n"] > 0
    assert not tmp_path.exists() or list(tmp_path.iterdir()) == []


def test_promotion_gate_closed_without_env_flags(tmp_path, monkeypatch):
    _clear_env(monkeypatch, tmp_path)
    rep = promote_candidate({"current_params": _current_params(), "proposed_params": _better_params()}, root=str(tmp_path))
    assert rep["ok"] is False
    assert rep["error_code"] == "SRLM_DISABLED"


def test_promotion_rejects_broken_witness(tmp_path, monkeypatch):
    _enable_promotion(monkeypatch, tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "growth_witness.jsonl").write_text("{}\n", encoding="utf-8")
    rep = promote_candidate({"current_params": _current_params(), "proposed_params": _better_params()}, root=str(tmp_path))
    assert rep["ok"] is False
    assert rep["error_code"] == "SRLM_WITNESS_INVALID"


def test_medium_high_risk_requires_human_review(tmp_path, monkeypatch):
    _enable_promotion(monkeypatch, tmp_path)
    rep = promote_candidate(
        {"current_params": _current_params(), "proposed_params": _better_params(), "risk_class": "med"},
        root=str(tmp_path),
    )
    assert rep["ok"] is False
    assert rep["error_code"] == "SRLM_HUMAN_REVIEW_REQUIRED"


def test_rollback_restores_previous_policy(tmp_path, monkeypatch):
    _enable_promotion(monkeypatch, tmp_path)
    write_promoted_policy(_current_params(), str(tmp_path))
    promoted = promote_candidate(
        {"current_params": _current_params(), "proposed_params": _better_params()},
        root=str(tmp_path),
    )
    assert promoted["ok"] is True
    assert load_promoted_policy(str(tmp_path))["router.local_weight"] == 0.8
    restored = rollback({"reason": "pytest"}, root=str(tmp_path))
    assert restored["ok"] is True
    assert load_promoted_policy(str(tmp_path))["router.local_weight"] == 0.0


def test_report_contains_fitness_curve_and_witness_status(tmp_path, monkeypatch):
    _enable_promotion(monkeypatch, tmp_path)
    promote_candidate({"current_params": _current_params(), "proposed_params": _better_params()}, root=str(tmp_path))
    rep = build_report(root=str(tmp_path))
    assert rep["ok"] is True
    assert "fitness_curve" in rep["fitness"]
    assert rep["witness"]["ok"] is True


def test_srlm_routes(tmp_path, monkeypatch):
    _clear_env(monkeypatch, tmp_path)
    app = Flask(__name__)
    register_srlm_routes(app)
    client = app.test_client()
    admin = {"X-User-Roles": "admin"}

    status = client.get("/srlm/status")
    assert status.status_code == 200
    assert status.get_json()["enabled"] is False

    shadow = client.post(
        "/srlm/shadow_step",
        headers=admin,
        json={"current_params": _current_params(), "proposed_params": _better_params()},
    )
    assert shadow.status_code == 403
    assert shadow.get_json()["error_code"] == "SRLM_DISABLED"

    promote = client.post(
        "/srlm/promote_candidate",
        headers=admin,
        json={"current_params": _current_params(), "proposed_params": _better_params()},
    )
    assert promote.status_code == 403

    monkeypatch.setenv("ESTER_SRLM_ENABLE", "1")
    bad_source = client.post(
        "/srlm/record_outcome",
        headers=admin,
        json={"episode_id": "e_model", "score": 0.2, "source": "model"},
    )
    assert bad_source.status_code == 400
    assert bad_source.get_json()["error_code"] == "FITNESS_SOURCE_INVALID"

    witness = client.get("/srlm/verify_witness")
    assert witness.status_code == 200
    assert "ok" in witness.get_json()
