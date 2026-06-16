# -*- coding: utf-8 -*-
import json
import os

import pytest

from growth_engine import (
    BehaviorVersion,
    Candidate,
    FitnessLedger,
    GrowthEngine,
    GrowthWitnessLedger,
    Outcome,
    PromotionGate,
    ReplaySet,
    new_version,
    propose_param_candidates,
    shadow_eval,
)
from growth_engine.candidates import RISK_LOW, RISK_MED


def _target(x):
    return 2.0 * x + 1.0


def _scorer(ctx, action):
    return 1.0 / (1.0 + abs(float(action) - _target(float(ctx["x"]))))


def _replay():
    return ReplaySet("t", [{"x": float(v)} for v in range(-5, 6)], _scorer)


def _enable(monkeypatch):
    monkeypatch.setenv("GROWTH_ENABLE", "1")
    monkeypatch.setenv("GROWTH_ACK_RISK", "I_UNDERSTAND")
    monkeypatch.setenv("GROWTH_ALLOW_PROMOTE", "1")
    monkeypatch.setenv("GROWTH_MAX_PROMOTIONS_PER_WINDOW", "50")


def _disable(monkeypatch):
    for k in ("GROWTH_ENABLE", "GROWTH_ACK_RISK", "GROWTH_ALLOW_PROMOTE"):
        monkeypatch.delenv(k, raising=False)


def _seed(engine, replay):
    for i, ctx in enumerate(replay.contexts):
        from growth_engine import decide

        engine.record_outcome(Outcome(f"ep{i}", _scorer(ctx, decide(engine.current.params, ctx)), "reality"))


# ---------------------------------------------------------------------------


def test_fitness_source_must_be_external(tmp_path):
    fl = FitnessLedger(str(tmp_path))
    bad = fl.record_outcome(Outcome("e1", 0.9, "model"))
    assert bad["ok"] is False and bad["error_code"] == "FITNESS_SOURCE_INVALID"
    for src in ("human", "reality", "l4"):
        assert fl.record_outcome(Outcome(f"e_{src}", 0.5, src))["ok"] is True


def test_fail_closed_by_default(tmp_path, monkeypatch):
    _disable(monkeypatch)
    replay = _replay()
    eng = GrowthEngine(root=str(tmp_path), replay=replay, initial=new_version({"w": 0.0, "bias": 0.0}), min_cluster=3)
    _seed(eng, replay)
    out = eng.step(seed=0)
    # either no candidate or a rejection with the gate closed - never a promotion
    assert out["action"] != "promoted"
    if out["action"] == "rejected":
        assert out["decision"]["error_code"] == "GROWTH_GATE_CLOSED"


def test_witness_chain_tamper_detected(tmp_path):
    w = GrowthWitnessLedger(str(tmp_path))
    w.append("promotion", {"candidate_id": "c1", "delta": "0.100000"})
    w.append("promotion", {"candidate_id": "c2", "delta": "0.200000"})
    assert w.verify_chain()["ok"] is True
    lines = w.path.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["subject"]["delta"] = "9.999999"
    lines[0] = json.dumps(row, ensure_ascii=True, separators=(",", ":"))
    w.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    v = w.verify_chain()
    assert v["ok"] is False and v["error_code"] in ("GROWTH_WITNESS_HASH_MISMATCH", "GROWTH_WITNESS_CHAIN_BROKEN")


def test_heldout_gate_blocks_bad_passes_good(tmp_path, monkeypatch):
    _enable(monkeypatch)
    replay = _replay()
    w = GrowthWitnessLedger(str(tmp_path))
    gate = PromotionGate(w, min_margin=0.01)
    current = new_version({"w": 0.0, "bias": 0.0})

    good = new_version({"w": 2.0, "bias": 1.0}, parent=current)  # the optimum
    bad = new_version({"w": -3.0, "bias": -5.0}, parent=current)  # worse
    cg = Candidate("cg", current.version_id, good, RISK_LOW, "good")
    cb = Candidate("cb", current.version_id, bad, RISK_LOW, "bad")

    eg = shadow_eval(replay, current, good)
    eb = shadow_eval(replay, current, bad)
    assert eg["delta"] > 0 and eb["delta"] < 0

    dg = gate.evaluate(current, cg, eg)
    db = gate.evaluate(current, cb, eb)
    assert dg["ok"] is True and dg["promoted"].version_id == good.version_id
    assert db["ok"] is False and db["error_code"] == "MARGIN_NOT_MET"


def test_med_risk_requires_human_approver(tmp_path, monkeypatch):
    _enable(monkeypatch)
    replay = _replay()
    w = GrowthWitnessLedger(str(tmp_path))
    gate = PromotionGate(w, min_margin=0.0)
    current = new_version({"w": 0.0, "bias": 0.0})
    good = new_version({"w": 2.0, "bias": 1.0}, parent=current)
    cand = Candidate("cm", current.version_id, good, RISK_MED, "prompt swap")
    ev = shadow_eval(replay, current, good)

    denied = gate.evaluate(current, cand, ev, approver=None)
    assert denied["ok"] is False and denied["error_code"] == "APPROVAL_FAILED"

    ok_ = gate.evaluate(current, cand, ev, approver=lambda c, e: True)
    assert ok_["ok"] is True


def test_l4_budget_enforced(tmp_path, monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setenv("GROWTH_MAX_PROMOTIONS_PER_WINDOW", "1")
    replay = _replay()
    w = GrowthWitnessLedger(str(tmp_path))
    gate = PromotionGate(w, min_margin=0.0)
    current = new_version({"w": 0.0, "bias": 0.0})
    v1 = new_version({"w": 1.0, "bias": 0.5}, parent=current)
    v2 = new_version({"w": 2.0, "bias": 1.0}, parent=v1)
    c1 = Candidate("c1", current.version_id, v1, RISK_LOW, "step1")
    c2 = Candidate("c2", v1.version_id, v2, RISK_LOW, "step2")

    d1 = gate.evaluate(current, c1, shadow_eval(replay, current, v1))
    assert d1["ok"] is True
    d2 = gate.evaluate(v1, c2, shadow_eval(replay, v1, v2))
    assert d2["ok"] is False and d2["error_code"] == "L4_BUDGET_EXHAUSTED"


def test_rollback_and_demote_are_witnessed(tmp_path):
    w = GrowthWitnessLedger(str(tmp_path))
    gate = PromotionGate(w)
    a = new_version({"w": 1.0, "bias": 0.0})
    b = new_version({"w": 2.0, "bias": 1.0}, parent=a)
    assert gate.rollback(a, reason="manual")["ok"] is True
    assert gate.demote(b, a, reason="decayed")["ok"] is True
    recs = [r["event_type"] for r in w.records()]
    assert "rollback" in recs and "demotion" in recs
    assert w.verify_chain()["ok"] is True


def test_growth_curve_rises(tmp_path, monkeypatch):
    _enable(monkeypatch)
    replay = _replay()
    eng = GrowthEngine(
        root=str(tmp_path),
        replay=replay,
        initial=new_version({"w": 0.0, "bias": 0.0}),
        min_cluster=3,
        proposal_n=24,
        proposal_step=1.0,
    )
    _seed(eng, replay)
    start = eng.live_fitness(eng.current)
    eng.run(30)
    end = eng.live_fitness(eng.current)
    rep = eng.growth_report()
    assert rep["counts"]["promotion"] >= 1
    assert len(rep["fitness_curve"]) >= 1
    assert end > start  # the system measurably improved on held-out
    assert rep["witness_chain"]["ok"] is True


def test_monitor_demotes_worse_current(tmp_path, monkeypatch):
    _enable(monkeypatch)
    replay = _replay()
    good = new_version({"w": 2.0, "bias": 1.0})
    eng = GrowthEngine(root=str(tmp_path), replay=replay, initial=good)
    # force a worse "current" and ensure monitor demotes back to good parent
    worse = new_version({"w": -2.0, "bias": -3.0}, parent=good)
    eng.current = worse
    res = eng.monitor_and_demote(good)
    assert res["action"] == "demoted" and eng.current.version_id == good.version_id
