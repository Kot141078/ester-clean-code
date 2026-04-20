# -*- coding: utf-8 -*-
from __future__ import annotations

from modules.proactivity import role_allocator


class _FakeSelector:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def chat(self, *args, **kwargs):
        return {"ok": True, "provider": "local", "answer": self.answer}


def test_role_allocator_applies_safe_template_choice(monkeypatch):
    monkeypatch.setenv("ESTER_SWARM_SELF_ROLE_ALLOCATOR_ENABLED", "1")
    monkeypatch.setenv("ESTER_SWARM_SELF_ROLE_ALLOCATOR_APPLY", "1")
    monkeypatch.setattr(
        role_allocator,
        "llm_selector",
        _FakeSelector(
            '{"selected_template_id":"builder.v1","team_templates":["builder.v1","planner.v1"],'
            '"branch_count":2,"needs_critic":true,"needs_synthesizer":true,'
            '"confidence":0.91,"reasoning":"Builder can own the safe artifact pass."}'
        ),
    )

    rep = role_allocator.allocate_for_initiative(
        {"title": "Investigate safe artifact issue", "text": "Почини safe artifact pipeline", "priority": "high"},
        plan_kind="repair_follow_up",
        fallback_template_id="clawbot.safe.v1",
        candidate_templates=["clawbot.safe.v1", "builder.v1", "planner.v1"],
        apply_templates=["clawbot.safe.v1", "builder.v1", "planner.v1"],
        source="test",
    )

    assert rep["selected_template_id"] == "builder.v1"
    assert rep["applied_template_id"] == "builder.v1"
    assert rep["apply_template"] is True
    assert rep["branch_count"] == 2
    assert rep["needs_critic"] is True
    assert rep["team_templates"] == ["builder.v1", "planner.v1"]


def test_role_allocator_keeps_fallback_on_invalid_output(monkeypatch):
    monkeypatch.setenv("ESTER_SWARM_SELF_ROLE_ALLOCATOR_ENABLED", "1")
    monkeypatch.setenv("ESTER_SWARM_SELF_ROLE_ALLOCATOR_APPLY", "1")
    monkeypatch.setattr(role_allocator, "llm_selector", _FakeSelector("not-json"))

    rep = role_allocator.allocate_for_goal(
        "Собери безопасный план по задаче",
        fallback_template_id="planner.v1",
        candidate_templates=["planner.v1", "builder.v1"],
        apply_templates=["planner.v1", "builder.v1"],
        source="test",
    )

    assert rep["selected_template_id"] == "planner.v1"
    assert rep["applied_template_id"] == "planner.v1"
    assert rep["apply_template"] is False

