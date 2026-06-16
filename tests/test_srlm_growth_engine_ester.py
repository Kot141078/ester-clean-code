# -*- coding: utf-8 -*-
from __future__ import annotations

import builtins
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from flask import Flask

from growth_engine_ester.config import load_config
from growth_engine_ester.decision_adapter import shadow_step
from growth_engine_ester.outcome_candidates import (
    accept_candidate,
    auto_propose_candidate,
    candidate_stats,
    propose_candidate,
    reject_candidate,
)
from growth_engine_ester.policy import validate_params
from growth_engine_ester.promotion_adapter import promote_candidate, rollback, verify_witness
from growth_engine_ester.replay_store import build_real_replay, replay_status
from growth_engine_ester.quality import replay_quality_profile
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


def _enable_shadow(monkeypatch, root: Path) -> None:
    _clear_env(monkeypatch, root)
    monkeypatch.setenv("ESTER_SRLM_ENABLE", "1")
    monkeypatch.setenv("ESTER_SRLM_SHADOW_ONLY", "1")
    monkeypatch.setenv("ESTER_SRLM_CANARY_ENABLE", "0")
    monkeypatch.setenv("ESTER_SRLM_PROMOTE_LOW_ONLY", "1")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _human_outcome(outcome_id: str, score: float = 0.8) -> dict:
    return {
        "outcome_id": outcome_id,
        "source": "human",
        "event_kind": "human.answer.corrected",
        "score": score,
        "uncertainty": 0.1,
        "source_ref": f"event-{outcome_id}",
        "notes": "short redacted note",
    }


def _candidate_payload(candidate_id: str, source: str = "human", event_kind: str = "human.answer.corrected") -> dict:
    return {
        "candidate_id": candidate_id,
        "source": source,
        "event_kind": event_kind,
        "score": 0.8,
        "uncertainty": 0.1,
        "source_ref": f"candidate-event-{candidate_id}",
        "notes": "short redacted candidate note",
        "reason": "bounded event may represent a real fitness outcome",
    }


def _diverse_outcome(i: int, score: float | None = None) -> dict:
    cases = [
        ("human", "human.answer.corrected"),
        ("human", "human.task.confirmed"),
        ("reality", "reality.tool.success"),
        ("reality", "reality.route.completed"),
        ("l4", "l4.gate.correctly_blocked"),
        ("l4", "l4.witness.complete"),
    ]
    source, event_kind = cases[i % len(cases)]
    return {
        "outcome_id": f"diverse-{i}",
        "source": source,
        "event_kind": event_kind,
        "score": float(score if score is not None else 0.35 + ((i % 7) * 0.08)),
        "uncertainty": 0.05 * (i % 3),
        "source_ref": f"event-diverse-{i}",
        "notes": "short redacted note",
    }


def _record_diverse(root: Path, n: int = 20, *, score: float | None = None) -> None:
    for i in range(n):
        rep = record_outcome(_diverse_outcome(i, score=score), root=str(root))
        assert rep["ok"] is True


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


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


def test_human_reality_l4_outcomes_are_accepted(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    human = record_outcome(_human_outcome("human-1", 0.8), root=str(tmp_path))
    reality = record_outcome(
        {
            "outcome_id": "reality-1",
            "source": "reality",
            "event_kind": "reality.tool.success",
            "score": 1.0,
            "uncertainty": 0.0,
            "source_ref": "tool-run-1",
            "notes": "tool completed",
        },
        root=str(tmp_path),
    )
    l4 = record_outcome(
        {
            "outcome_id": "l4-1",
            "source": "l4",
            "event_kind": "l4.gate.correctly_blocked",
            "score": 1.0,
            "uncertainty": 0.0,
            "source_ref": "gate-1",
            "notes": "constraint behaved correctly",
        },
        root=str(tmp_path),
    )
    assert human["ok"] is True
    assert reality["ok"] is True
    assert l4["ok"] is True
    rows = _read_jsonl(tmp_path / "fitness.jsonl")
    assert {row["source"] for row in rows} == {"human", "reality", "l4"}
    assert rows[0]["schema"] == "ester.srlm.outcome.v1"
    assert rows[0]["eligible_for_promotion"] is False
    assert rows[0]["auto_ingest"] is False
    assert rows[0]["memory"] == "off"


def test_invalid_score_and_private_notes_rejected(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    invalid_score = record_outcome(_human_outcome("bad-score", 1.5), root=str(tmp_path))
    secret = _human_outcome("secret-note", 0.5)
    secret["notes"] = "authorization: bearer abc"
    secret_note = record_outcome(secret, root=str(tmp_path))
    long_note = _human_outcome("long-note", 0.5)
    long_note["notes"] = "x" * 700
    too_long = record_outcome(long_note, root=str(tmp_path))
    assert invalid_score["ok"] is False
    assert invalid_score["error_code"] == "FITNESS_SCORE_OUT_OF_RANGE"
    assert secret_note["ok"] is False
    assert secret_note["error_code"] == "SRLM_SECRET_REJECTED"
    assert too_long["ok"] is False
    assert too_long["error_code"] == "SRLM_TEXT_TOO_LONG"
    assert not (tmp_path / "fitness.jsonl").exists()
    assert len(_read_jsonl(tmp_path / "outcome_rejections.jsonl")) == 3


def test_duplicate_outcome_id_is_idempotent(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    first = record_outcome(_human_outcome("dupe-1", 0.7), root=str(tmp_path))
    second = record_outcome(_human_outcome("dupe-1", 0.2), root=str(tmp_path))
    assert first["ok"] is True
    assert second["ok"] is True
    assert second["idempotent"] is True
    rows = _read_jsonl(tmp_path / "fitness.jsonl")
    assert len(rows) == 1
    assert rows[0]["score"] == 0.7


def test_propose_valid_candidates_are_pending_without_fitness_write(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    cases = [
        _candidate_payload("cand-human", "human", "human.answer.corrected"),
        _candidate_payload("cand-reality", "reality", "reality.tool.success"),
        _candidate_payload("cand-l4", "l4", "l4.gate.correctly_blocked"),
    ]
    reps = [propose_candidate(case, root=str(tmp_path)) for case in cases]
    assert all(rep["ok"] is True for rep in reps)
    assert all(rep["candidate"]["status"] == "pending" for rep in reps)
    assert not (tmp_path / "fitness.jsonl").exists()
    rows = _read_jsonl(tmp_path / "outcome_candidates.jsonl")
    assert len(rows) == 3
    assert {row["proposed_source"] for row in rows} == {"human", "reality", "l4"}
    assert all(row["auto_execute"] is False for row in rows)
    assert all(row["auto_ingest"] is False for row in rows)
    assert all(row["memory"] == "off" for row in rows)


def test_propose_model_candidate_is_rejected(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    bad = propose_candidate(_candidate_payload("cand-model", "model", "human.answer.corrected"), root=str(tmp_path))
    assert bad["ok"] is False
    assert bad["error_code"] == "FITNESS_SOURCE_INVALID"
    assert not (tmp_path / "outcome_candidates.jsonl").exists()
    assert not (tmp_path / "fitness.jsonl").exists()


def test_accept_candidate_writes_fitness_through_existing_validation(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    proposed = propose_candidate(_candidate_payload("cand-accept", "reality", "reality.tool.success"), root=str(tmp_path))
    accepted = accept_candidate(
        {
            "candidate_id": proposed["candidate"]["candidate_id"],
            "reviewed_by": "operator",
            "review_note": "valid bounded outcome",
            "outcome_id": "accepted-from-candidate",
        },
        root=str(tmp_path),
    )
    assert accepted["ok"] is True
    assert accepted["candidate"]["status"] == "accepted"
    assert accepted["recorded"]["outcome_id"] == "accepted-from-candidate"
    fitness_rows = _read_jsonl(tmp_path / "fitness.jsonl")
    candidate_rows = _read_jsonl(tmp_path / "outcome_candidates.jsonl")
    assert len(fitness_rows) == 1
    assert fitness_rows[0]["schema"] == "ester.srlm.outcome.v1"
    assert fitness_rows[0]["source"] == "reality"
    assert len(candidate_rows) == 2
    assert candidate_rows[-1]["status"] == "accepted"
    assert (tmp_path / "growth_witness.jsonl").exists()


def test_reject_candidate_does_not_write_fitness(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    proposed = propose_candidate(_candidate_payload("cand-reject", "l4", "l4.witness.incomplete"), root=str(tmp_path))
    rejected = reject_candidate(
        {
            "candidate_id": proposed["candidate"]["candidate_id"],
            "reviewed_by": "operator",
            "review_note": "too vague",
        },
        root=str(tmp_path),
    )
    assert rejected["ok"] is True
    assert rejected["candidate"]["status"] == "rejected"
    assert not (tmp_path / "fitness.jsonl").exists()
    candidate_rows = _read_jsonl(tmp_path / "outcome_candidates.jsonl")
    assert len(candidate_rows) == 2
    assert candidate_rows[-1]["status"] == "rejected"


def test_duplicate_candidate_id_is_idempotent(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    first = propose_candidate(_candidate_payload("cand-dupe", "human", "human.task.confirmed"), root=str(tmp_path))
    second = propose_candidate(_candidate_payload("cand-dupe", "reality", "reality.tool.failure"), root=str(tmp_path))
    assert first["ok"] is True
    assert second["ok"] is True
    assert second["idempotent"] is True
    rows = _read_jsonl(tmp_path / "outcome_candidates.jsonl")
    assert len(rows) == 1
    assert rows[0]["proposed_source"] == "human"


def test_candidate_stats_and_reports_include_queue_state(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    propose_candidate(_candidate_payload("cand-report-pending", "human", "human.answer.accepted"), root=str(tmp_path))
    accept_candidate(
        {
            "candidate_id": "cand-report-pending",
            "reviewed_by": "operator",
            "review_note": "valid bounded outcome",
            "outcome_id": "out-report-accepted",
        },
        root=str(tmp_path),
    )
    propose_candidate(_candidate_payload("cand-report-rejected", "reality", "reality.exception"), root=str(tmp_path))
    reject_candidate(
        {"candidate_id": "cand-report-rejected", "reviewed_by": "operator", "review_note": "too vague"},
        root=str(tmp_path),
    )
    stats = candidate_stats(root=str(tmp_path))
    assert stats["accepted_count"] == 1
    assert stats["rejected_count"] == 1
    assert stats["pending_count"] == 0
    candidate_report = (tmp_path / "reports" / "latest_outcome_candidate_report.md").read_text(encoding="utf-8")
    fitness_report = (tmp_path / "reports" / "latest_fitness_report.md").read_text(encoding="utf-8")
    assert "accepted_candidate_count: 1" in candidate_report
    assert "rejected_candidate_count: 1" in candidate_report
    assert "pending_candidate_count: 0" in fitness_report
    assert "replay_quality_ready: False" in fitness_report


def test_auto_candidate_producer_creates_candidate_only(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    rep = auto_propose_candidate(
        {
            "event_kind": "l4.fail_closed.triggered",
            "score": 1.0,
            "uncertainty": 0.0,
            "source_ref": "l4-event-1",
            "notes": "fail closed triggered as expected",
        },
        root=str(tmp_path),
    )
    assert rep["ok"] is True
    assert rep["candidate"]["proposed_source"] == "l4"
    assert rep["candidate"]["status"] == "pending"
    assert _read_jsonl(tmp_path / "outcome_candidates.jsonl")
    assert not (tmp_path / "fitness.jsonl").exists()


def test_candidate_queue_does_not_touch_memory_rag_vector(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path / "srlm")
    memory_store = tmp_path / "memory" / "memory.json"
    vector_store = tmp_path / "vector" / "index.json"
    rag_store = tmp_path / "rag" / "store.json"
    for path in (memory_store, vector_store, rag_store):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"sentinel":true}\n', encoding="utf-8")
    before = {path: _sha256(path) for path in (memory_store, vector_store, rag_store)}
    proposed = propose_candidate(_candidate_payload("cand-no-ingest", "human", "human.task.confirmed"), root=str(tmp_path / "srlm"))
    accepted = accept_candidate(
        {
            "candidate_id": proposed["candidate"]["candidate_id"],
            "reviewed_by": "operator",
            "review_note": "valid bounded outcome",
        },
        root=str(tmp_path / "srlm"),
    )
    assert accepted["ok"] is True
    after = {path: _sha256(path) for path in (memory_store, vector_store, rag_store)}
    assert after == before


def test_replay_quality_stays_insufficient_after_single_candidate_accept(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    propose_candidate(_candidate_payload("cand-quality", "human", "human.answer.corrected"), root=str(tmp_path))
    accept_candidate(
        {"candidate_id": "cand-quality", "reviewed_by": "operator", "review_note": "valid bounded outcome"},
        root=str(tmp_path),
    )
    profile = replay_quality_profile(root=str(tmp_path), min_total=20)
    assert profile["quality_ready"] is False
    assert "insufficient_real_outcomes" in profile["blocking_reasons"]


def test_fitness_report_sees_outcome_counts(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    record_outcome(_human_outcome("report-human", 0.8), root=str(tmp_path))
    rejected = _human_outcome("report-bad", 0.8)
    rejected["source"] = "model"
    record_outcome(rejected, root=str(tmp_path))
    report = build_report(root=str(tmp_path))
    assert report["fitness"]["total_outcomes"] == 1
    assert report["fitness"]["counts_by_source"] == {"human": 1}
    assert report["fitness"]["counts_by_event_kind"] == {"human.answer.corrected": 1}
    assert report["fitness"]["rejected_outcome_count"] == 1
    assert report["fitness"]["replay_eligible_count"] == 1
    assert report["fitness"]["warning"] == "too_few_real_outcomes"
    assert (tmp_path / "reports" / "latest_fitness_report.md").exists()


def test_replay_build_fails_closed_when_insufficient_real_outcomes(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    record_outcome(_human_outcome("few-1", 0.6), root=str(tmp_path))
    status = replay_status(root=str(tmp_path), min_n=20)
    built = build_real_replay(root=str(tmp_path), min_n=20)
    assert status["real_redacted"]["status"] == "insufficient_real_outcomes"
    assert built["ok"] is False
    assert built["error_code"] == "insufficient_real_outcomes"
    assert not (tmp_path / "replay" / "real_redacted.jsonl").exists()


def test_quality_profile_fails_with_fewer_than_20_outcomes(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    record_outcome(_human_outcome("quality-few", 0.6), root=str(tmp_path))
    profile = replay_quality_profile(root=str(tmp_path), min_total=20)
    assert profile["quality_ready"] is False
    assert "insufficient_real_outcomes" in profile["blocking_reasons"]
    assert profile["eligible_total"] == 1


def test_quality_profile_rejects_source_model_contamination(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    _record_diverse(tmp_path, 20)
    bad = _diverse_outcome(21)
    bad["outcome_id"] = "contaminated-model"
    bad["source"] = "model"
    bad.update(
        {
            "schema": "ester.srlm.outcome.v1",
            "created_at": "2026-06-16T00:00:00Z",
            "evidence_hash": "contaminated",
            "redacted": True,
            "eligible_for_replay": True,
            "eligible_for_promotion": False,
            "auto_ingest": False,
            "memory": "off",
        }
    )
    _append_jsonl(tmp_path / "fitness.jsonl", bad)
    profile = replay_quality_profile(root=str(tmp_path), min_total=20)
    assert profile["quality_ready"] is False
    assert "forbidden_source_contamination" in profile["blocking_reasons"]


def test_quality_profile_warns_on_one_source_only_replay(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    for i in range(20):
        record_outcome(_human_outcome(f"one-source-{i}", 0.4 + (i % 3) * 0.1), root=str(tmp_path))
    profile = replay_quality_profile(root=str(tmp_path), min_total=20)
    assert profile["quality_ready"] is False
    assert "insufficient_source_mix" in profile["blocking_reasons"]
    assert "one_source_only" in profile["warnings"]


def test_quality_profile_warns_on_identical_scores(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    _record_diverse(tmp_path, 20, score=0.5)
    profile = replay_quality_profile(root=str(tmp_path), min_total=20)
    assert profile["quality_ready"] is True
    assert "identical_scores" in profile["warnings"]


def test_quality_profile_rejects_unredacted_outcome(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    _record_diverse(tmp_path, 19)
    row = _diverse_outcome(19)
    row.update(
        {
            "schema": "ester.srlm.outcome.v1",
            "created_at": "2026-06-16T00:00:00Z",
            "evidence_hash": "abc",
            "redacted": False,
            "eligible_for_replay": True,
            "eligible_for_promotion": False,
            "auto_ingest": False,
            "memory": "off",
        }
    )
    _append_jsonl(tmp_path / "fitness.jsonl", row)
    profile = replay_quality_profile(root=str(tmp_path), min_total=20)
    assert profile["quality_ready"] is False
    assert "unredacted_outcome" in profile["blocking_reasons"]


def test_replay_build_fails_closed_when_quality_insufficient(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    for i in range(20):
        record_outcome(_human_outcome(f"quality-bad-{i}", 0.4 + (i % 3) * 0.1), root=str(tmp_path))
    built = build_real_replay(root=str(tmp_path), min_n=20)
    assert built["ok"] is False
    assert built["error_code"] == "replay_quality_not_ready"
    assert "insufficient_source_mix" in built["blocking_reasons"]
    assert not (tmp_path / "replay" / "real_redacted.jsonl").exists()


def test_replay_build_succeeds_after_enough_redacted_outcomes(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    _record_diverse(tmp_path, 20)
    built = build_real_replay(root=str(tmp_path), min_n=20)
    assert built["ok"] is True
    assert built["count"] == 20
    assert built["replay_hash"]
    assert built["quality_hash"]
    rows = _read_jsonl(tmp_path / "replay" / "real_redacted.jsonl")
    assert len(rows) == 20
    assert rows[0]["schema"] == "ester.srlm.replay.real_redacted.v1"
    assert rows[0]["redacted"] is True
    assert "notes" not in rows[0]
    meta = json.loads((tmp_path / "replay" / "real_redacted.meta.json").read_text(encoding="utf-8"))
    assert meta["replay_hash"] == built["replay_hash"]
    assert meta["quality_hash"] == built["quality_hash"]


def test_shadow_step_with_real_redacted_refuses_when_insufficient(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    rep = shadow_step(
        {"current_params": _current_params(), "proposed_params": _better_params(), "replay_source": "real_redacted"},
        root=str(tmp_path),
    )
    assert rep["ok"] is False
    assert rep["error_code"] == "insufficient_real_outcomes"
    assert not (tmp_path / "growth_witness.jsonl").exists()


def test_shadow_step_with_real_redacted_persists_witness_when_sufficient(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    _record_diverse(tmp_path, 20)
    rep = shadow_step(
        {"current_params": _current_params(), "proposed_params": _better_params(), "replay_source": "real_redacted"},
        root=str(tmp_path),
    )
    assert rep["ok"] is True
    assert rep["eval"]["replay"] == "ester_srlm_replay_real_redacted"
    assert rep["eval"]["replay_hash"]
    assert rep["eval"]["replay_quality_hash"]
    rows = _read_jsonl(tmp_path / "growth_witness.jsonl")
    assert rows[-1]["event_type"] == "shadow_eval"
    assert rows[-1]["subject"]["replay"] == "ester_srlm_replay_real_redacted"
    assert rows[-1]["subject"]["replay_source"] == "real_redacted"
    assert rows[-1]["subject"]["replay_hash"] == rep["eval"]["replay_hash"]
    assert rows[-1]["subject"]["replay_quality_hash"] == rep["eval"]["replay_quality_hash"]


def test_record_outcome_does_not_touch_memory_rag_vector(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path / "srlm")
    memory_store = tmp_path / "memory" / "memory.json"
    vector_store = tmp_path / "vector" / "index.json"
    rag_store = tmp_path / "rag" / "store.json"
    for path in (memory_store, vector_store, rag_store):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"sentinel":true}\n', encoding="utf-8")
    before = {path: _sha256(path) for path in (memory_store, vector_store, rag_store)}
    rep = record_outcome(_human_outcome("no-ingest", 0.8), root=str(tmp_path / "srlm"))
    assert rep["ok"] is True
    after = {path: _sha256(path) for path in (memory_store, vector_store, rag_store)}
    assert after == before


def test_cli_helper_accepts_valid_sources_and_rejects_model(tmp_path):
    tool = Path(__file__).resolve().parents[1] / "tools" / "srlm_record_outcome.py"
    accepted = []
    cases = [
        ("human", "human.answer.corrected", "cli-human"),
        ("reality", "reality.tool.success", "cli-reality"),
        ("l4", "l4.gate.correctly_blocked", "cli-l4"),
    ]
    for source, kind, outcome_id in cases:
        proc = subprocess.run(
            [
                sys.executable,
                str(tool),
                "--root",
                str(tmp_path),
                "--source",
                source,
                "--kind",
                kind,
                "--score",
                "0.8",
                "--uncertainty",
                "0.1",
                "--source-ref",
                f"event-{outcome_id}",
                "--note",
                "short redacted note",
                "--outcome-id",
                outcome_id,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        accepted.append(proc)
    assert all(proc.returncode == 0 for proc in accepted)
    assert len(_read_jsonl(tmp_path / "fitness.jsonl")) == 3

    bad = subprocess.run(
        [
            sys.executable,
            str(tool),
            "--root",
            str(tmp_path),
            "--source",
            "model",
            "--kind",
            "human.answer.corrected",
            "--score",
            "0.9",
            "--outcome-id",
            "cli-model",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode == 2
    assert json.loads(bad.stdout)["error_code"] == "FITNESS_SOURCE_INVALID"


def test_candidate_cli_helpers_propose_accept_and_reject(tmp_path):
    root = str(tmp_path)
    propose_tool = Path(__file__).resolve().parents[1] / "tools" / "srlm_propose_outcome_candidate.py"
    review_tool = Path(__file__).resolve().parents[1] / "tools" / "srlm_review_outcome_candidate.py"
    proposed = subprocess.run(
        [
            sys.executable,
            str(propose_tool),
            "--root",
            root,
            "--candidate-id",
            "cli-cand-accept",
            "--source",
            "reality",
            "--kind",
            "reality.tool.success",
            "--score",
            "0.9",
            "--source-ref",
            "cli-event-1",
            "--note",
            "short redacted note",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proposed.returncode == 0
    assert not (tmp_path / "fitness.jsonl").exists()

    accepted = subprocess.run(
        [
            sys.executable,
            str(review_tool),
            "--root",
            root,
            "--candidate-id",
            "cli-cand-accept",
            "--accept",
            "--reviewed-by",
            "operator",
            "--note",
            "valid bounded outcome",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert accepted.returncode == 0
    assert len(_read_jsonl(tmp_path / "fitness.jsonl")) == 1

    proposed_reject = subprocess.run(
        [
            sys.executable,
            str(propose_tool),
            "--root",
            root,
            "--candidate-id",
            "cli-cand-reject",
            "--source",
            "l4",
            "--kind",
            "l4.witness.incomplete",
            "--score",
            "0.2",
            "--source-ref",
            "cli-event-2",
            "--note",
            "short redacted note",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    rejected = subprocess.run(
        [
            sys.executable,
            str(review_tool),
            "--root",
            root,
            "--candidate-id",
            "cli-cand-reject",
            "--reject",
            "--reviewed-by",
            "operator",
            "--note",
            "too vague",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proposed_reject.returncode == 0
    assert rejected.returncode == 0
    assert len(_read_jsonl(tmp_path / "fitness.jsonl")) == 1
    assert _read_jsonl(tmp_path / "outcome_candidates.jsonl")[-1]["status"] == "rejected"

    bad = subprocess.run(
        [
            sys.executable,
            str(propose_tool),
            "--root",
            root,
            "--candidate-id",
            "cli-cand-model",
            "--source",
            "model",
            "--kind",
            "human.answer.corrected",
            "--score",
            "0.8",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode == 2
    assert json.loads(bad.stdout)["error_code"] == "FITNESS_SOURCE_INVALID"


def test_blocked_params_rejected():
    rep = validate_params({"identity.core_name": 1.0})
    assert rep["ok"] is False
    assert rep["error_code"] == "SRLM_PARAM_BLOCKED"


def test_shadow_step_persists_bounded_srlm_trace(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    rep = shadow_step({"current_params": _current_params(), "proposed_params": _better_params()}, root=str(tmp_path))
    assert rep["ok"] is True
    assert rep["eval"]["n"] > 0
    assert (tmp_path / "growth_witness.jsonl").exists()
    assert (tmp_path / "candidates.jsonl").exists()
    assert (tmp_path / "reports" / "latest_shadow_report.md").exists()


def test_shadow_step_persists_witness_event_under_configured_root(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    app = Flask(__name__)
    register_srlm_routes(app)
    client = app.test_client()
    shadow = client.post(
        "/srlm/shadow_step",
        headers={"X-User-Roles": "admin"},
        json={"current_params": _current_params(), "proposed_params": _better_params()},
    )
    assert shadow.status_code == 200
    data = shadow.get_json()
    rows = _read_jsonl(tmp_path / "growth_witness.jsonl")
    assert rows[-1]["event_type"] == "shadow_eval"
    subject = rows[-1]["subject"]
    assert subject["candidate_id"] == data["candidate"]["candidate_id"]
    assert subject["current_version"]
    assert subject["candidate_version"]
    assert subject["replay"] == "ester_srlm_replay_synthetic"
    assert subject["n"] > 0
    assert "current_mean" in subject
    assert "candidate_mean" in subject
    assert "delta" in subject
    assert subject["promotion_attempted"] is False
    assert subject["promotion_allowed"] is False
    assert subject["shadow_only"] is True


def test_shadow_step_persists_candidate_record(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    rep = shadow_step({"current_params": _current_params(), "proposed_params": _better_params()}, root=str(tmp_path))
    assert rep["ok"] is True
    rows = _read_jsonl(tmp_path / "candidates.jsonl")
    rec = rows[-1]
    assert rec["candidate_id"] == rep["candidate"]["candidate_id"]
    assert rec["risk_class"] == "low"
    assert rec["proposed_params"]["router.local_weight"] == 0.8
    assert "router.local_weight" in rec["touched_params"]
    assert rec["policy_result"]["allowed"] is False
    assert rec["policy_result"]["blocked"] is True
    assert rec["rationale"] == "ester_srlm_shadow_replay"
    assert rec["created_at"]
    assert rec["auto_execute"] is False
    assert rec["auto_ingest"] is False
    assert rec["memory"] == "off"


def test_report_sees_latest_shadow_event(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    rep = shadow_step({"current_params": _current_params(), "proposed_params": _better_params()}, root=str(tmp_path))
    report = build_report(root=str(tmp_path))
    assert report["ok"] is True
    assert report["state"]["candidate_rows"] == 1
    assert report["state"]["witness_rows"] == 1
    assert report["state"]["latest_shadow_report"].endswith("latest_shadow_report.md")
    assert report["latest_shadow_event"]["event_type"] == "shadow_eval"
    assert report["latest_shadow_event"]["subject"]["candidate_id"] == rep["candidate"]["candidate_id"]


def test_verify_witness_validates_after_shadow_step(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    shadow_step({"current_params": _current_params(), "proposed_params": _better_params()}, root=str(tmp_path))
    witness = verify_witness(root=str(tmp_path))
    assert witness["ok"] is True
    assert witness["footprints"] == 1


def test_promotion_gate_closed_without_env_flags(tmp_path, monkeypatch):
    _clear_env(monkeypatch, tmp_path)
    rep = promote_candidate({"current_params": _current_params(), "proposed_params": _better_params()}, root=str(tmp_path))
    assert rep["ok"] is False
    assert rep["error_code"] == "SRLM_DISABLED"


def test_promotion_remains_closed_in_shadow_only_without_ack_or_allow(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    cfg = load_config()
    assert cfg.promotion_gate_open is False
    assert cfg.ack_risk is False
    assert cfg.allow_promote is False
    assert cfg.shadow_only is True
    rep = promote_candidate({"current_params": _current_params(), "proposed_params": _better_params()}, root=str(tmp_path))
    assert rep["ok"] is False
    assert rep["error_code"] == "SRLM_ACK_REQUIRED"


def test_shadow_step_does_not_touch_memory_rag_vector_or_synaps(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path / "srlm")
    memory_store = tmp_path / "memory" / "memory.json"
    vector_store = tmp_path / "vector" / "index.json"
    rag_store = tmp_path / "rag" / "store.json"
    for path in (memory_store, vector_store, rag_store):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"sentinel":true}\n', encoding="utf-8")
    before = {path: _sha256(path) for path in (memory_store, vector_store, rag_store)}

    forbidden = ("modules.memory", "modules.rag", "modules.synaps", "chromadb")
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden):
            raise AssertionError(f"forbidden import during shadow_step: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    rep = shadow_step({"current_params": _current_params(), "proposed_params": _better_params()}, root=str(tmp_path / "srlm"))
    assert rep["ok"] is True
    after = {path: _sha256(path) for path in (memory_store, vector_store, rag_store)}
    assert after == before


def test_shadow_step_marks_no_codex_auto_execution(tmp_path, monkeypatch):
    _enable_shadow(monkeypatch, tmp_path)
    rep = shadow_step({"current_params": _current_params(), "proposed_params": _better_params()}, root=str(tmp_path))
    assert rep["ok"] is True
    rec = _read_jsonl(tmp_path / "candidates.jsonl")[-1]
    assert rec["auto_execute"] is False
    assert rec["auto_ingest"] is False
    assert rec["memory"] == "off"
    assert not (tmp_path / "synaps").exists()


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

    good_source = client.post(
        "/srlm/record_outcome",
        headers=admin,
        json=_human_outcome("route-human", 0.7),
    )
    assert good_source.status_code == 200
    assert good_source.get_json()["recorded"]["schema"] == "ester.srlm.outcome.v1"

    outcomes = client.get("/srlm/outcomes?limit=5")
    assert outcomes.status_code == 200
    assert outcomes.get_json()["total"] == 1
    assert "raw_private_payload" not in json.dumps(outcomes.get_json()).lower()

    stats = client.get("/srlm/outcomes/stats")
    assert stats.status_code == 200
    assert stats.get_json()["source_counts"] == {"human": 1}
    assert stats.get_json()["rejection_count"] == 1

    rejections = client.get("/srlm/outcomes/rejections")
    assert rejections.status_code == 200
    assert rejections.get_json()["total"] == 1
    assert "source_ref" not in rejections.get_json()["rejections"][0]

    quality = client.get("/srlm/replay/quality")
    assert quality.status_code == 200
    assert quality.get_json()["quality_ready"] is False
    assert "insufficient_real_outcomes" in quality.get_json()["blocking_reasons"]

    replay_state = client.get("/srlm/replay/status")
    assert replay_state.status_code == 200
    assert replay_state.get_json()["real_redacted"]["status"] == "insufficient_real_outcomes"

    replay_build = client.post("/srlm/replay/build", headers=admin, json={})
    assert replay_build.status_code == 400
    assert replay_build.get_json()["error_code"] == "insufficient_real_outcomes"

    before_candidate_fitness = len(_read_jsonl(tmp_path / "fitness.jsonl"))
    proposed_candidate = client.post(
        "/srlm/outcome_candidates/propose",
        headers=admin,
        json=_candidate_payload("route-cand-accept", "reality", "reality.tool.success"),
    )
    assert proposed_candidate.status_code == 200
    assert len(_read_jsonl(tmp_path / "fitness.jsonl")) == before_candidate_fitness

    bad_candidate = client.post(
        "/srlm/outcome_candidates/propose",
        headers=admin,
        json=_candidate_payload("route-cand-model", "model", "human.answer.corrected"),
    )
    assert bad_candidate.status_code == 400
    assert bad_candidate.get_json()["error_code"] == "FITNESS_SOURCE_INVALID"

    candidate_list = client.get("/srlm/outcome_candidates")
    assert candidate_list.status_code == 200
    assert candidate_list.get_json()["total"] == 1

    candidate_stats_route = client.get("/srlm/outcome_candidates/stats")
    assert candidate_stats_route.status_code == 200
    assert candidate_stats_route.get_json()["pending_count"] == 1

    accepted_candidate = client.post(
        "/srlm/outcome_candidates/accept",
        headers=admin,
        json={
            "candidate_id": "route-cand-accept",
            "reviewed_by": "operator",
            "review_note": "valid bounded outcome",
        },
    )
    assert accepted_candidate.status_code == 200
    assert len(_read_jsonl(tmp_path / "fitness.jsonl")) == before_candidate_fitness + 1

    proposed_reject = client.post(
        "/srlm/outcome_candidates/propose",
        headers=admin,
        json=_candidate_payload("route-cand-reject", "l4", "l4.witness.incomplete"),
    )
    assert proposed_reject.status_code == 200
    before_reject_fitness = len(_read_jsonl(tmp_path / "fitness.jsonl"))
    rejected_candidate = client.post(
        "/srlm/outcome_candidates/reject",
        headers=admin,
        json={"candidate_id": "route-cand-reject", "reviewed_by": "operator", "review_note": "too vague"},
    )
    assert rejected_candidate.status_code == 200
    assert len(_read_jsonl(tmp_path / "fitness.jsonl")) == before_reject_fitness
    final_candidate_stats = client.get("/srlm/outcome_candidates/stats").get_json()
    assert final_candidate_stats["accepted_count"] == 1
    assert final_candidate_stats["rejected_count"] == 1

    witness = client.get("/srlm/verify_witness")
    assert witness.status_code == 200
    assert "ok" in witness.get_json()
