# -*- coding: utf-8 -*-
from __future__ import annotations

from modules.garage.templates import registry as template_registry
from modules.thinking import action_registry


def test_plan_build_registered_and_invokable():
    ids = set(action_registry.list_action_ids())
    assert "plan.build" in ids

    rep = action_registry.run("plan.build", {"goal": "offline smoke"})
    assert rep.get("ok") is True
    assert isinstance(rep.get("plan"), dict)
    assert isinstance(rep.get("plan_text"), str)
    assert str(rep.get("plan_text") or "").strip()


def test_planner_template_uses_plan_build_without_skip_fallback():
    spec = template_registry.render_spec("planner.v1", {})
    assert "plan.build" in list(spec.get("allowed_actions") or [])

    plan = template_registry.render_plan("planner.v1", {})
    steps = list(plan.get("steps") or [])
    assert any(str(step.get("action_id")) == "plan.build" for step in steps)

    skipped_plan_build = [
        step
        for step in steps
        if str(((step.get("args") or {}).get("meta") or {}).get("skipped_action") or "") == "plan.build"
    ]
    assert skipped_plan_build == []
