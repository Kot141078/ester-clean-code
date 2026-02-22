# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List


PACK_V1: List[Dict[str, Any]] = [
    {
        "id": "archivist.v1",
        "title": "Archivist",
        "description": "Write a compact local archive note and notify outbox.",
        "default_name": "garage.archivist",
        "default_goal": "Create a compact archive artifact and publish completion note.",
        "capabilities": [
            "cap.fs.sandbox.write",
            "cap.messages.outbox",
            "cap.memory.note",
        ],
        "default_allowed_actions": ["fs.write", "memory.add_note", "messages.outbox.enqueue"],
        "default_budgets": {"max_steps": 6, "max_work_ms": 3000, "window_sec": 60, "est_work_ms": 300},
        "default_scopes": {"fs_roots": ["data/garage/sandbox"], "network": "disabled"},
        "default_plan": [
            {
                "action_id": "fs.write",
                "args": {
                    "relpath": "sandbox/archivist_note.txt",
                    "content": "archivist.v1 note for {name}: {goal}",
                },
            },
            {
                "action_id": "memory.add_note",
                "args": {
                    "text": "archivist.v1 archived note for {name}: {goal}",
                    "tags": ["garage", "archivist", "iter69"],
                    "source": "garage.templates.archivist.v1",
                },
            },
            {
                "action_id": "messages.outbox.enqueue",
                "args": {
                    "kind": "garage.agent.done",
                    "text": "archivist.v1 completed for {name}",
                    "meta": {"template_id": "archivist.v1"},
                },
            },
        ],
        "oracle_policy": {"enabled": False, "requires_window": True},
        "comm_policy": {"enabled": False, "requires_window": True},
    },
    {
        "id": "dreamer.v1",
        "title": "Dreamer",
        "description": "Run a single dream generation cycle and publish status.",
        "default_name": "garage.dreamer",
        "default_goal": "Generate one safe dream artifact and report completion.",
        "default_allowed_actions": ["dreams.run_once", "messages.outbox.enqueue"],
        "default_budgets": {"max_steps": 4, "max_work_ms": 2500, "window_sec": 60, "est_work_ms": 250},
        "default_scopes": {"network": "disabled"},
        "default_plan": [
            {
                "action_id": "dreams.run_once",
                "args": {"source": "garage.templates.dreamer.v1"},
            },
            {
                "action_id": "messages.outbox.enqueue",
                "args": {
                    "kind": "garage.agent.done",
                    "text": "dreamer.v1 dream created for {name}",
                    "meta": {"template_id": "dreamer.v1"},
                },
            },
        ],
        "oracle_policy": {"enabled": False, "requires_window": True},
        "comm_policy": {"enabled": False, "requires_window": True},
    },
    {
        "id": "initiator.v1",
        "title": "Initiator",
        "description": "Create lightweight initiative intent and notify outbox.",
        "default_name": "garage.initiator",
        "default_goal": "Queue one initiative and report.",
        "capabilities": [
            "cap.memory.note",
            "cap.fs.sandbox.write",
            "cap.fs.sha256.verify",
            "cap.proactivity.queue.add",
            "cap.initiative.mark_done",
            "cap.messages.outbox",
        ],
        "default_allowed_actions": [
            "initiatives.run_once",
            "proactivity.queue.add",
            "initiative.mark_done",
            "messages.outbox.enqueue",
        ],
        "default_budgets": {"max_steps": 5, "max_work_ms": 3000, "window_sec": 60, "est_work_ms": 300},
        "default_scopes": {"network": "disabled"},
        "default_plan": [
            {
                "action_id": "initiatives.run_once",
                "args": {"source": "garage.templates.initiator.v1"},
            },
            {
                "action_id": "proactivity.queue.add",
                "args": {
                    "title": "Initiative from {name}",
                    "text": "{goal}",
                    "priority": "normal",
                    "source": "garage.templates.initiator.v1",
                },
            },
            {
                "action_id": "messages.outbox.enqueue",
                "args": {
                    "kind": "garage.agent.done",
                    "text": "initiator.v1 queued initiative for {name}",
                    "meta": {"template_id": "initiator.v1"},
                },
            },
        ],
        "oracle_policy": {"enabled": False, "requires_window": True},
        "comm_policy": {"enabled": False, "requires_window": True},
    },
    {
        "id": "planner.v1",
        "title": "Planner",
        "description": "Build a plan draft and save it inside sandbox.",
        "default_name": "garage.planner",
        "default_goal": "Produce a small actionable plan draft.",
        "default_allowed_actions": ["plan.build", "fs.write", "messages.outbox.enqueue"],
        "default_budgets": {"max_steps": 5, "max_work_ms": 3000, "window_sec": 60, "est_work_ms": 300},
        "default_scopes": {"fs_roots": ["data/garage/plans"], "network": "disabled"},
        "default_plan": [
            {
                "action_id": "plan.build",
                "args": {"goal": "{goal}", "source": "garage.templates.planner.v1"},
            },
            {
                "action_id": "fs.write",
                "args": {
                    "relpath": "plans/plan_draft.txt",
                    "content": "Plan draft for {name}\nGoal: {goal}\n1) Observe\n2) Execute safely\n3) Report",
                },
            },
            {
                "action_id": "messages.outbox.enqueue",
                "args": {
                    "kind": "garage.agent.done",
                    "text": "planner.v1 plan draft prepared for {name}",
                    "meta": {"template_id": "planner.v1"},
                },
            },
        ],
        "oracle_policy": {"enabled": False, "requires_window": True},
        "comm_policy": {"enabled": False, "requires_window": True},
    },
    {
        "id": "builder.v1",
        "title": "Builder",
        "description": "Create and verify a small artifact in sandbox.",
        "default_name": "garage.builder",
        "default_goal": "Create a sandbox artifact and verify hash.",
        "capabilities": [
            "cap.fs.sandbox.write",
            "cap.fs.sha256.verify",
            "cap.messages.outbox",
            "cap.memory.note",
        ],
        "default_allowed_actions": ["fs.write", "fs.patch", "fs.hash", "messages.outbox.enqueue"],
        "default_budgets": {"max_steps": 6, "max_work_ms": 3500, "window_sec": 60, "est_work_ms": 350},
        "default_scopes": {"fs_roots": ["data/garage/sandbox"], "network": "disabled"},
        "default_plan": [
            {
                "action_id": "fs.write",
                "args": {
                    "relpath": "sandbox/builder_artifact.txt",
                    "content": "builder.v1 artifact for {name}: {goal}",
                },
            },
            {
                "action_id": "fs.patch",
                "args": {
                    "relpath": "sandbox/builder_artifact.txt",
                    "content": "builder.v1 artifact for {name}: {goal}\npatch: applied",
                },
            },
            {
                "action_id": "fs.hash",
                "args": {
                    "relpath": "sandbox/builder_artifact.txt",
                    "expected_sha256": "__AUTO_FROM_WRITE__",
                },
            },
            {
                "action_id": "messages.outbox.enqueue",
                "args": {
                    "kind": "garage.agent.done",
                    "text": "builder.v1 finished artifact for {name}",
                    "meta": {"template_id": "builder.v1"},
                },
            },
        ],
        "oracle_policy": {"enabled": False, "requires_window": True},
        "comm_policy": {"enabled": False, "requires_window": True},
    },
    {
        "id": "clawbot.safe.v1",
        "title": "Clawbot Safe (Plan-Only)",
        "description": "Draft a structured clawbot plan artifact for operator review (no execution).",
        "default_name": "garage.clawbot.safe",
        "default_goal": "Draft a safe clawbot plan for operator review",
        "capabilities": [
            "cap.fs.sandbox.write",
            "cap.fs.sha256.verify",
            "cap.messages.outbox",
            "cap.memory.note",
        ],
        "default_allowed_actions": ["fs.write", "fs.patch", "fs.hash", "memory.add_note", "messages.outbox.enqueue"],
        "default_budgets": {"max_steps": 6, "max_work_ms": 3500, "window_sec": 60, "est_work_ms": 300},
        "default_scopes": {"fs_roots": ["data/garage/sandbox"], "network": "disabled"},
        "queue_policy": {"requires_approval": True},
        "default_plan": [
            {
                "action_id": "fs.write",
                "args": {
                    "relpath": "sandbox/clawbot_safe_plan.md",
                    "content": (
                        "# clawbot.safe.v1 plan\n"
                        "- name: {name}\n"
                        "- goal: {goal}\n"
                        "- mode: plan-only\n"
                        "- execution: operator review required\n"
                        "## steps\n"
                        "1. Inspect workspace constraints.\n"
                        "2. Draft safe clawbot sequence.\n"
                        "3. Hand off to operator for approval.\n"
                    ),
                },
            },
            {
                "action_id": "fs.hash",
                "args": {
                    "relpath": "sandbox/clawbot_safe_plan.md",
                    "expected_sha256": "__AUTO_FROM_WRITE__",
                },
            },
            {
                "action_id": "memory.add_note",
                "args": {
                    "text": "clawbot.safe.v1 drafted plan for {name}: {goal}",
                    "tags": ["garage", "clawbot", "safe", "plan-only"],
                    "source": "garage.templates.clawbot.safe.v1",
                },
            },
            {
                "action_id": "messages.outbox.enqueue",
                "args": {
                    "kind": "garage.agent.done",
                    "text": "clawbot.safe.v1 prepared operator plan for {name}",
                    "meta": {"template_id": "clawbot.safe.v1", "mode": "plan_only"},
                },
            },
        ],
        "oracle_policy": {"enabled": False, "requires_window": True},
        "comm_policy": {"enabled": False, "requires_window": True},
    },
    {
        "id": "reviewer.v1",
        "title": "Reviewer",
        "description": "Run offline checks workflow and report summary.",
        "default_name": "garage.reviewer",
        "default_goal": "Run quality checks and emit concise report.",
        "default_allowed_actions": [
            "run_checks_offline",
            "route_registry_check",
            "route_return_lint",
            "messages.outbox.enqueue",
        ],
        "default_budgets": {"max_steps": 5, "max_work_ms": 3000, "window_sec": 60, "est_work_ms": 300},
        "default_scopes": {"network": "disabled"},
        "default_plan": [
            {
                "action_id": "run_checks_offline",
                "args": {"source": "garage.templates.reviewer.v1"},
            },
            {
                "action_id": "route_registry_check",
                "args": {"source": "garage.templates.reviewer.v1"},
            },
            {
                "action_id": "route_return_lint",
                "args": {"source": "garage.templates.reviewer.v1"},
            },
            {
                "action_id": "messages.outbox.enqueue",
                "args": {
                    "kind": "garage.agent.done",
                    "text": "reviewer.v1 checks summary prepared for {name}",
                    "meta": {"template_id": "reviewer.v1"},
                },
            },
        ],
        "oracle_policy": {"enabled": False, "requires_window": True},
        "comm_policy": {"enabled": False, "requires_window": True},
    },
    {
        "id": "runner.v1",
        "title": "Runner",
        "description": "Run nested safe execution and publish status.",
        "default_name": "garage.runner",
        "default_goal": "Execute nested safe plan and summarize outcome.",
        "default_allowed_actions": ["agent.run_once", "messages.outbox.enqueue"],
        "default_budgets": {"max_steps": 4, "max_work_ms": 2500, "window_sec": 60, "est_work_ms": 250},
        "default_scopes": {"network": "disabled"},
        "default_plan": [
            {
                "action_id": "agent.run_once",
                "args": {"mode": "safe", "source": "garage.templates.runner.v1"},
            },
            {
                "action_id": "messages.outbox.enqueue",
                "args": {
                    "kind": "garage.agent.done",
                    "text": "runner.v1 nested run finished for {name}",
                    "meta": {"template_id": "runner.v1"},
                },
            },
        ],
        "oracle_policy": {"enabled": False, "requires_window": True},
        "comm_policy": {"enabled": False, "requires_window": True},
    },
    {
        "id": "curiosity_researcher",
        "title": "Curiosity Researcher",
        "description": "Investigate unknown ticket via local evidence and crystallize result.",
        "default_name": "garage.curiosity.researcher",
        "default_goal": "Resolve unknown ticket with evidence and L4W references.",
        "default_allowed_actions": [
            "local.search",
            "local.extract",
            "local.crosscheck",
            "crystallize.fact",
            "crystallize.negative",
            "close.ticket",
            "web.search",
        ],
        "default_budgets": {"max_steps": 7, "max_work_ms": 2500, "window_sec": 120, "est_work_ms": 250},
        "default_scopes": {"network": "disabled_by_default"},
        "default_plan": [
            {
                "action_id": "local.search",
                "args": {"ticket_id": "{goal}", "query": "{goal}", "max_docs": 12},
            },
            {
                "action_id": "local.extract",
                "args": {"ticket_id": "{goal}", "query": "{goal}", "top_k": 8},
            },
            {
                "action_id": "local.crosscheck",
                "args": {"ticket_id": "{goal}", "query": "{goal}", "min_sources": 2},
            },
            {
                "action_id": "crystallize.fact",
                "args": {"ticket_id": "{goal}", "query": "{goal}"},
            },
            {
                "action_id": "close.ticket",
                "args": {"ticket_id": "{goal}", "default_event": "resolve"},
            },
        ],
        "oracle_policy": {"enabled": False, "requires_window": True},
        "comm_policy": {"enabled": False, "requires_window": True},
    },
    {
        "id": "oracle.v1",
        "title": "Oracle",
        "description": "Remote oracle call template with strict default OFF policy.",
        "default_name": "garage.oracle",
        "default_goal": "Use remote oracle only with explicit admin-enabled window.",
        "capabilities": [
            "cap.oracle.remote.call",
            "cap.fs.sandbox.write",
            "cap.messages.outbox",
        ],
        "default_allowed_actions": ["llm.remote.call", "messages.outbox.enqueue"],
        "default_budgets": {"max_steps": 3, "max_work_ms": 2500, "window_sec": 60, "est_work_ms": 250},
        "default_scopes": {"network": "disabled_by_default"},
        "default_plan": [
            {
                "action_id": "messages.outbox.enqueue",
                "args": {
                    "kind": "garage.agent.note",
                    "text": "oracle.v1 is disabled by default; enable oracle window explicitly.",
                    "meta": {"template_id": "oracle.v1", "oracle_enabled": False},
                },
            }
        ],
        "plan_when_oracle_enabled": [
            {
                "action_id": "llm.remote.call",
                "args": {
                    "prompt": "Summarize goal for {name}: {goal}",
                    "model": "gpt-4o-mini",
                    "reason": "garage.templates.oracle.v1",
                    "window_id": "{window_id}",
                    "dry_run": True,
                },
            },
            {
                "action_id": "messages.outbox.enqueue",
                "args": {
                    "kind": "garage.agent.done",
                    "text": "oracle.v1 completed dry-run remote request for {name}",
                    "meta": {"template_id": "oracle.v1", "oracle_enabled": True},
                },
            },
        ],
        "oracle_policy": {"enabled": False, "requires_window": True, "allow_hosts": ["api.openai.com"]},
        "comm_policy": {"enabled": False, "requires_window": True},
    },
]


def by_id() -> Dict[str, Dict[str, Any]]:
    return {str(t.get("id")): dict(t) for t in PACK_V1 if str(t.get("id") or "").strip()}


__all__ = ["PACK_V1", "by_id"]
