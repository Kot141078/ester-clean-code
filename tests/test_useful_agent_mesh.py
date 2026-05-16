# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from modules.agents import governed_mesh
from modules.garage import agent_factory, agent_queue, agent_runner


def test_task_contract_rejects_redline_permissions():
    contract = governed_mesh.build_task_contract("sentinel", "agent_test")
    contract["permissions"]["memory_write"] = True

    rep = governed_mesh.validate_task_contract(contract)

    assert rep["ok"] is False
    assert rep["decision"] == "deny_and_quarantine"
    assert "permission_forbidden_memory_write" in rep["errors"]


def test_task_contract_rejects_unrestricted_network():
    contract = governed_mesh.build_task_contract("auditor", "agent_test")
    contract["network_policy"] = {"mode": "unrestricted", "allowed_endpoints": ["*"]}

    rep = governed_mesh.validate_task_contract(contract)

    assert rep["ok"] is False
    assert rep["decision"] == "deny_and_quarantine"
    assert "network_unrestricted" in rep["errors"]


def test_reconcile_creates_stable_bounded_roster(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_USEFUL_AGENT_MESH_ROLES", "sentinel,auditor")
    monkeypatch.setenv("ESTER_USEFUL_AGENT_MESH_CREATE_BATCH", "8")
    monkeypatch.setenv("ESTER_VOLITION_SLOT", "A")

    first = governed_mesh.reconcile(create_missing=True)
    second = governed_mesh.reconcile(create_missing=True)

    assert first["ok"] is True
    assert first["registered_total"] == 2
    assert first["created_total"] == 2
    assert second["ok"] is True
    assert second["registered_total"] == 2
    assert second["created_total"] == 0
    rows = second["roles_requested"]
    assert rows == ["sentinel", "auditor"]
    agents = agent_factory.list_agents()
    assert agents["total"] == 2


def test_enqueue_due_tasks_are_contractual_and_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_USEFUL_AGENT_MESH_ROLES", "sentinel,auditor,tester")
    monkeypatch.setenv("ESTER_USEFUL_AGENT_MESH_MAX_ENQUEUE_PER_TICK", "2")
    monkeypatch.setenv("ESTER_USEFUL_AGENT_MESH_MAX_LIVE", "2")
    monkeypatch.setenv("ESTER_USEFUL_AGENT_MESH_TASK_INTERVAL_SEC", "60")
    monkeypatch.setenv("ESTER_VOLITION_SLOT", "A")

    governed_mesh.reconcile(create_missing=True)
    rep = governed_mesh.enqueue_due_tasks(force=True)

    assert rep["ok"] is True
    assert rep["enqueued_total"] == 2
    state = agent_queue.fold_state()
    live = [x for x in state["live"] if (x.get("plan") or {}).get("meta", {}).get("governed_mesh")]
    assert len(live) == 2
    for item in live:
        plan = item["plan"]
        contract = plan["steps"][0]["args"]["contract"]
        assert governed_mesh.validate_task_contract(contract)["ok"] is True
        assert plan["meta"]["governed_mesh"] is True


def test_legacy_proactivity_enqueue_is_denied_without_governed_mesh_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.delenv("ESTER_PROACTIVITY_LEGACY_AGENT_QUEUE_ENABLED", raising=False)
    monkeypatch.setenv("ESTER_VOLITION_SLOT", "A")
    monkeypatch.setattr(agent_queue, "_agent_enabled_state", lambda aid: True)
    monkeypatch.setattr(agent_queue, "_agent_requires_approval", lambda aid: None)

    rep = agent_queue.enqueue(
        {
            "plan_id": "plan_legacy_proactivity",
            "steps": [{"action": "messages.outbox.enqueue", "args": {"text": "legacy"}}],
            "meta": {"plan_kind": "repair_follow_up"},
        },
        queue_id="q_legacy_proactivity",
        agent_id="agent_legacy",
        actor="ester",
        reason="proactivity_enqueue:initiative_legacy",
        challenge_sec=0,
    )

    assert rep["ok"] is False
    assert rep["error"] == "legacy_proactivity_queue_denied"
    assert agent_queue.fold_state()["live_total"] == 0


def test_governed_mesh_enqueue_is_still_allowed_with_proactivity_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.delenv("ESTER_PROACTIVITY_LEGACY_AGENT_QUEUE_ENABLED", raising=False)
    monkeypatch.setenv("ESTER_USEFUL_AGENT_MESH_ROLES", "sentinel")
    monkeypatch.setenv("ESTER_VOLITION_SLOT", "A")

    governed_mesh.reconcile(create_missing=True)
    rep = governed_mesh.enqueue_due_tasks(force=True)

    assert rep["ok"] is True
    assert rep["enqueued_total"] == 1
    state = agent_queue.fold_state()
    assert state["live_total"] == 1
    item = state["live"][0]
    assert item["plan"]["meta"]["governed_mesh"] is True


def test_role_report_runs_through_agent_runner(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_USEFUL_AGENT_MESH_ROLES", "sentinel")
    monkeypatch.setenv("ESTER_VOLITION_SLOT", "A")

    rec = governed_mesh.reconcile(create_missing=True)
    agent_id = rec["created"][0]["agent_id"]
    contract = governed_mesh.build_task_contract("sentinel", agent_id)
    plan = governed_mesh.build_role_plan("sentinel", agent_id, contract)

    rep = agent_runner.run_once(agent_id, plan, {"intent": "test_useful_mesh", "chain_id": "chain_test"})

    assert rep["ok"] is True
    assert rep["status"] == "done"
    artifact = Path(rep["steps"][0]["result"]["artifact_path"])
    assert artifact.exists()
    text = artifact.read_text(encoding="utf-8")
    assert "Useful Agent Mesh Role Report" in text
    assert "direct_memory_write: denied" in text
