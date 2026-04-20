# -*- coding: utf-8 -*-
from __future__ import annotations

from modules.proactivity import planner_v2


def _step(plan, action_id):
    for row in list(plan.get("steps") or []):
        action = str(row.get("action") or row.get("action_id") or "")
        if action == action_id:
            return row
    raise AssertionError(f"step {action_id} not found")


def test_planner_v2_marks_repair_as_clawbot_auto():
    plan = planner_v2.build_plan(
        {
            "id": "initiative_repair_1",
            "title": "Investigate GTAV stutter",
            "text": "Проверь, почему GTAV тормозит и что именно мешает.",
            "kind": "repair_follow_up",
            "priority": "high",
            "score": 96,
        },
        {"max_work_ms": 1800, "max_actions": 6, "window": 60},
    )

    write_step = _step(plan, "files.sandbox_write")

    assert plan["meta"]["planner_version"] == "v2"
    assert plan["meta"]["target_template_id"] == "clawbot.safe.v1"
    assert plan["meta"]["execution_track"] == "clawbot_auto"
    assert plan["meta"]["queue_policy"]["requires_approval"] is False
    assert len(list(plan["meta"].get("subtasks") or [])) >= 3
    assert "definition_of_done" in plan["meta"]
    assert "## subtasks" in write_step["args"]["content"]
    assert "## escalate_if" in write_step["args"]["content"]


def test_planner_v2_keeps_care_ping_inline():
    plan = planner_v2.build_plan(
        {
            "id": "initiative_care_1",
            "title": "Warm follow up",
            "text": "Доброе утро Эстер, как ты сегодня?",
            "kind": "care_ping",
            "priority": "low",
            "score": 44,
        },
        {"max_work_ms": 1800, "max_actions": 6, "window": 60},
    )

    outbox_step = _step(plan, "messages.outbox.enqueue")

    assert plan["meta"]["target_template_id"] == "planner.v1"
    assert plan["meta"]["execution_track"] == "planner_inline"
    assert plan["meta"]["queue_policy"]["requires_approval"] is False
    assert "ждёт операторского подтверждения" not in outbox_step["args"]["text"]


def test_planner_v2_propagates_shared_chat_context_into_outbox_meta():
    plan = planner_v2.build_plan(
        {
            "id": "initiative_group_1",
            "title": "Investigate silent swarm in group chat",
            "text": "Проверь, почему агенты почти не работают в общем чате.",
            "kind": "repair_follow_up",
            "priority": "high",
            "score": 96,
            "meta": {
                "chat_id": "777",
                "user_id": "42",
                "chat_type": "group",
                "shared_chat": True,
                "speaker_name": "IVAN",
            },
        },
        {"max_work_ms": 1800, "max_actions": 6, "window": 60},
    )

    outbox_step = _step(plan, "messages.outbox.enqueue")
    outbox_meta = dict(outbox_step["args"].get("meta") or {})

    assert outbox_meta["chat_id"] == "777"
    assert outbox_meta["shared_chat"] is True
    assert outbox_meta["participant_kind"] == "agent"


def test_planner_v2_can_apply_self_role_allocator(monkeypatch):
    monkeypatch.setattr(
        planner_v2.role_allocator,
        "allocate_for_initiative",
        lambda *args, **kwargs: {
            "selected_template_id": "builder.v1",
            "applied_template_id": "builder.v1",
            "apply_template": True,
            "candidate_templates": ["clawbot.safe.v1", "builder.v1", "planner.v1"],
            "team_templates": ["builder.v1", "planner.v1"],
            "branch_count": 2,
            "needs_critic": True,
            "needs_synthesizer": True,
            "confidence": 0.93,
            "reasoning": "Builder should own the safe artifact pass.",
            "via": "self_role_allocator",
        },
    )

    plan = planner_v2.build_plan(
        {
            "id": "initiative_repair_allocated",
            "title": "Investigate safe artifact issue",
            "text": "Проверь safe artifact pipeline и подготовь безопасный next step.",
            "kind": "repair_follow_up",
            "priority": "high",
        },
        {"max_work_ms": 1800, "max_actions": 6, "window": 60},
    )

    subtasks = list(plan["meta"].get("subtasks") or [])

    assert plan["meta"]["target_template_id"] == "builder.v1"
    assert plan["meta"]["execution_track"] == "swarm_role_auto"
    assert plan["meta"]["execution_profile"]["role_allocation"]["branch_count"] == 2
    assert subtasks[0]["owner_hint"] == "builder.v1"
    assert subtasks[1]["owner_hint"] == "planner.v1"
