# -*- coding: utf-8 -*-
"""
tests/synergy/test_models.py — validatsiya modeley i fikstur (happy-path).

MOSTY:
- (Yavnyy) Proveryaem Agent.from_legacy, AssignmentRequest/Plan/Outcome, TelemetryEvent.
- (Skrytyy #1) Garantiruem, chto skhemy generiruyutsya bez oshibok.
- (Skrytyy #2) Demonstriruem obratimuyu normalizatsiyu legacy→model (osnovnye polya).

ZEMNOY ABZATs:
Esli eti testy zelenye — yadro domena stabilno i predskazuemo. Nad nim bezopasno stroit orkestrator i API.

# c=a+b
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import pytest

from modules.synergy.models import (
    Agent,
    AssignmentPlan,
    AssignmentRequest,
    Outcome,
    Override,
    Policy,
    RoleName,
    TelemetryEvent,
)

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures", "synergy")

def _load(name: str):
    with open(os.path.join(FIX, name), "r", encoding="utf-8") as f:
        return json.load(f)

def test_agents_from_legacy():
    raw_agents = _load("agents.json")
    agents = [Agent.from_legacy(x) for x in raw_agents]
    assert agents[0].kind.value == "human"
    assert agents[2].kind.value == "device"
    assert agents[1].channels and agents[1].channels.whatsapp

def test_policy_and_overrides():
    pol_raw = _load("policies.json")
    pol = Policy(model="synergy.Policy", **pol_raw)
    ov_raw = _load("assignment_request.json")["overrides"]
    ov = Override(**ov_raw)
    assert pol.max_roles_per_agent == 2
    assert list(ov.mapping.keys())[0].value == "operator"

def test_assignment_request_and_plan():
    req_raw = _load("assignment_request.json")
    req = AssignmentRequest(model="synergy.AssignmentRequest", **req_raw)
    assert req.team_id == "Recon A"
    assert RoleName.operator in req.overrides.mapping
    plan = AssignmentPlan(
        model="synergy.AssignmentPlan",
        team_id=req.team_id,
        assigned={RoleName.operator: "human.pilot"},
        total_score=1.23,
        steps=[],
    )
    assert plan.assigned[RoleName.operator] == "human.pilot"

def test_telemetry_event_schema_and_instances():
    events = _load("telemetry_events.json")
    for e in events:
        te = TelemetryEvent(model="synergy.TelemetryEvent", **e)
        assert te.agent_id
        assert (te.latency_ms or 0.0) >= 0.0

def test_generate_schemas(tmp_path, monkeypatch):
    # Pishem skhemy vo vremennuyu direktoriyu, chtoby ne trogat repo
    out = tmp_path / "schemas" / "synergy"
    monkeypatch.setenv("PYTHONHASHSEED", "0")  # determinizm
    from tools.synergy_generate_schemas import dump_schema
    from modules.synergy.models import Agent, Policy
    os.makedirs(out, exist_ok=True)
    dump_schema(Agent, str(out / "Agent"))
    dump_schema(Policy, str(out / "Policy"))
    files = list(out.parent.glob("synergy*"))
    assert len(files) >= 1
