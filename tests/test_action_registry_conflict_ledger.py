# -*- coding: utf-8 -*-
from __future__ import annotations

from modules.thinking.action_registry import invoke_guarded
from modules.volition import conflict_ledger
from modules.volition.volition_gate import VolitionContext, VolitionGate


def _network_ctx() -> VolitionContext:
    return VolitionContext(
        chain_id="chain_conflict_test",
        step="action",
        actor="ester",
        intent="network probe",
        action_kind="network.probe",
        needs=["network"],
        budgets={"max_actions": 3, "max_work_ms": 2000},
        metadata={"action_id": "network.probe", "args_digest": "network-args-digest"},
    )


def test_slot_b_gate_deny_records_conflict_without_changing_deny(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_SLOT", "B")
    monkeypatch.setenv("ESTER_ALLOW_NETWORK", "0")
    monkeypatch.setenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")

    rep = invoke_guarded(
        "network.probe",
        {"api_key": "SECRET_TOKEN", "query": "hello"},
        ctx=_network_ctx(),
        gate=VolitionGate(),
    )

    assert rep["ok"] is False
    assert rep["error"] == "volition_denied"
    assert rep["reason_code"] == "DENY_NETWORK"

    rows = conflict_ledger.tail(5)
    assert rows[-1]["source"] == "volition_gate.deny"
    assert rows[-1]["reason_code"] == "DENY_NETWORK"
    raw = conflict_ledger.conflicts_path().read_text(encoding="utf-8")
    raw += conflict_ledger.state_path().read_text(encoding="utf-8")
    assert "SECRET_TOKEN" not in raw


def test_ledger_failure_does_not_allow_denied_action(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_SLOT", "B")
    monkeypatch.setenv("ESTER_ALLOW_NETWORK", "0")
    monkeypatch.setenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")

    def boom(**_kwargs):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(conflict_ledger, "record_conflict", boom)
    rep = invoke_guarded("network.probe", {}, ctx=_network_ctx(), gate=VolitionGate())

    assert rep["ok"] is False
    assert rep["error"] == "volition_denied"
    assert rep["reason_code"] == "DENY_NETWORK"


def test_slot_a_observe_would_allow_behavior_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_SLOT", "A")
    monkeypatch.setenv("ESTER_ALLOW_NETWORK", "0")
    monkeypatch.setenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")

    rep = invoke_guarded("network.probe", {}, ctx=_network_ctx(), gate=VolitionGate())

    assert rep["ok"] is False
    assert rep["error"] == "unknown_action"
    assert rep["volition"]["allowed"] is True
    assert rep["volition"]["reason_code"] == "ALLOW_SLOT_A"
    assert rep["volition"]["policy_snapshot"]["would_allow"] is False
    rows = conflict_ledger.tail(5)
    assert rows[-1]["source"] == "volition_gate.observe"
    assert rows[-1]["reason_code"] == "DENY_NETWORK"


def test_oracle_deny_records_downstream_conflict_without_raw_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_VOLITION_SLOT", "A")
    monkeypatch.setenv("ESTER_ALLOW_NETWORK", "0")
    monkeypatch.setenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")

    rep = invoke_guarded(
        "llm.remote.call",
        {
            "prompt": "RAW_PROMPT_SHOULD_NOT_APPEAR",
            "purpose": "conflict ledger test",
            "max_tokens": 8,
        },
        ctx=VolitionContext(
            chain_id="chain_oracle_conflict_test",
            step="action",
            actor="ester",
            intent="oracle conflict test",
            action_kind="llm.remote.call",
            needs=["network"],
            budgets={"max_actions": 3, "max_work_ms": 2000},
            metadata={"action_id": "llm.remote.call"},
        ),
        gate=VolitionGate(),
    )

    assert rep["ok"] is False
    assert rep["error"].startswith("oracle_")
    rows = conflict_ledger.tail(10)
    assert any(row["source"] == "action_registry.oracle" for row in rows)
    raw = conflict_ledger.conflicts_path().read_text(encoding="utf-8")
    raw += conflict_ledger.state_path().read_text(encoding="utf-8")
    assert "RAW_PROMPT_SHOULD_NOT_APPEAR" not in raw
