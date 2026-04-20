# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from modules.proactivity import planner_v1, role_allocator


def _step(plan: Dict[str, Any], action_id: str) -> Dict[str, Any]:
    for row in list(plan.get("steps") or []):
        action = str(row.get("action") or row.get("action_id") or "").strip()
        if action == action_id:
            return row
    return {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _topic(initiative: Dict[str, Any], meta: Dict[str, Any]) -> str:
    for key in ("title", "text"):
        text = str(initiative.get(key) or "").strip()
        if text:
            return text[:120]
    return str(meta.get("focus") or "current task")[:120]


def _initiative_meta(initiative: Dict[str, Any]) -> Dict[str, Any]:
    return dict(initiative.get("meta") or {})


def _conversation_meta(initiative: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    src = _initiative_meta(initiative)
    shared_chat = bool(src.get("shared_chat") or meta.get("shared_chat"))
    out: Dict[str, Any] = {
        "chat_id": str(src.get("chat_id") or meta.get("chat_id") or "").strip(),
        "user_id": str(src.get("user_id") or meta.get("user_id") or "").strip(),
        "chat_type": str(src.get("chat_type") or meta.get("chat_type") or "").strip(),
        "speaker_name": str(src.get("speaker_name") or meta.get("speaker_name") or "").strip(),
        "shared_chat": shared_chat,
    }
    if shared_chat:
        out["participant_kind"] = "agent"
    return out


def _execution_profile(kind: str, initiative: Dict[str, Any]) -> Dict[str, Any]:
    priority = str(initiative.get("priority") or "normal").strip().lower()
    high_value = kind in {"repair_follow_up", "research_follow_up", "task_follow_up"}
    if high_value or priority in {"high", "urgent", "critical"}:
        profile = {
            "mode": "clawbot_autonomous",
            "target_template_id": "clawbot.safe.v1",
            "requires_approval": False,
            "queue_priority": 70,
            "approval_scope": "",
            "handoff_reason": "Safe clawbot execution can run autonomously and report after completion.",
        }
    elif kind in {"book_follow_up", "dream_follow_up"}:
        profile = {
            "mode": "guided_follow_up",
            "target_template_id": "planner.v1",
            "requires_approval": False,
            "queue_priority": 45,
            "approval_scope": "",
            "handoff_reason": "Keep it as a compact guided follow-up.",
        }
    else:
        profile = {
            "mode": "direct_proactivity",
            "target_template_id": "planner.v1",
            "requires_approval": False,
            "queue_priority": 50,
            "approval_scope": "",
            "handoff_reason": "Safe direct execution is sufficient.",
        }

    allocation = role_allocator.allocate_for_initiative(
        dict(initiative or {}),
        plan_kind=kind,
        fallback_template_id=str(profile.get("target_template_id") or "planner.v1"),
        candidate_templates=role_allocator.candidate_templates_for_kind(
            kind,
            fallback_template_id=str(profile.get("target_template_id") or "planner.v1"),
        ),
        apply_templates=["planner.v1", "builder.v1", "clawbot.safe.v1"],
        source="planner_v2",
    )
    applied_template_id = str(allocation.get("applied_template_id") or profile.get("target_template_id") or "planner.v1").strip() or "planner.v1"
    if applied_template_id != str(profile.get("target_template_id") or ""):
        profile["handoff_reason"] = (
            f"{str(profile.get('handoff_reason') or '').strip()} "
            f"Role allocator applied {applied_template_id}."
        ).strip()
    profile["target_template_id"] = applied_template_id
    if applied_template_id == "clawbot.safe.v1":
        profile["mode"] = "clawbot_autonomous"
    elif applied_template_id != "planner.v1":
        profile["mode"] = "swarm_role_auto"
    profile["role_allocation"] = {
        "selected_template_id": str(allocation.get("selected_template_id") or ""),
        "applied_template_id": applied_template_id,
        "apply_template": bool(allocation.get("apply_template")),
        "candidate_templates": [str(x) for x in list(allocation.get("candidate_templates") or []) if str(x).strip()],
        "team_templates": [str(x) for x in list(allocation.get("team_templates") or []) if str(x).strip()],
        "branch_count": _safe_int(allocation.get("branch_count"), 1),
        "needs_critic": bool(allocation.get("needs_critic")),
        "needs_synthesizer": bool(allocation.get("needs_synthesizer")),
        "confidence": allocation.get("confidence"),
        "reasoning": str(allocation.get("reasoning") or "").strip(),
        "via": str(allocation.get("via") or ""),
    }
    return profile


def _owner_hint_for_subtask(profile: Dict[str, Any], idx: int) -> str:
    alloc = dict(profile.get("role_allocation") or {})
    team = [str(x) for x in list(alloc.get("team_templates") or []) if str(x).strip()]
    if team:
        return team[idx % len(team)]
    return str(profile.get("target_template_id") or "planner.v1")


def _subtasks(kind: str, topic: str, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    def tail(idx: int) -> Dict[str, Any]:
        return {
            "owner_hint": _owner_hint_for_subtask(profile, idx),
            "escalate_on": ["conflicting_signal", "missing_context", "more_than_one_next_step"],
        }

    if kind == "repair_follow_up":
        return [
            {
                "id": "triage_signal",
                "objective": f"Bound the concrete symptom around: {topic}",
                "deliverable": "One bounded symptom statement with scope.",
                "definition_of_done": "The symptom is stated without generic filler and without mixing multiple problems.",
                **tail(0),
            },
            {
                "id": "rank_hypotheses",
                "objective": "List the most plausible causes in descending order.",
                "deliverable": "Two or three hypotheses with one recommended first check.",
                "definition_of_done": "Each hypothesis is testable and tied to the observed symptom.",
                **tail(1),
            },
            {
                "id": "prepare_safe_check",
                "objective": "Choose the smallest safe next verification step.",
                "deliverable": "One safe next step plus the signal that would confirm or reject it.",
                "definition_of_done": "The next step is concrete, reversible, and does not require privileged action.",
                **tail(2),
            },
        ]
    if kind == "research_follow_up":
        return [
            {
                "id": "restate_question",
                "objective": f"Restate the core question behind: {topic}",
                "deliverable": "A single clean question statement.",
                "definition_of_done": "The question is explicit and free from unrelated side topics.",
                **tail(0),
            },
            {
                "id": "map_hypotheses",
                "objective": "Map the competing explanations or answer paths.",
                "deliverable": "Two or three explicit hypotheses or angles.",
                "definition_of_done": "Each angle is distinct and can be checked further.",
                **tail(1),
            },
            {
                "id": "operator_handoff",
                "objective": "Prepare the concise handoff for operator review.",
                "deliverable": "A recommended path plus what would change the recommendation.",
                "definition_of_done": "The handoff contains one recommendation and one escalation trigger.",
                **tail(2),
            },
        ]
    if kind == "task_follow_up":
        return [
            {
                "id": "scope_task",
                "objective": f"Reduce the initiative to one concrete work unit: {topic}",
                "deliverable": "One bounded unit of work with a clear output.",
                "definition_of_done": "The unit of work can be finished in one swarm pass.",
                **tail(0),
            },
            {
                "id": "pick_owner",
                "objective": "Choose the best swarm role for the work.",
                "deliverable": "A recommended owner role and why it fits.",
                "definition_of_done": "The chosen owner is justified by capability and risk level.",
                **tail(1),
            },
            {
                "id": "set_done_line",
                "objective": "Define how completion will be recognized.",
                "deliverable": "A short definition of done and one escalation condition.",
                "definition_of_done": "Completion can be judged without guessing.",
                **tail(2),
            },
        ]
    if kind == "book_follow_up":
        return [
            {
                "id": "extract_anchor",
                "objective": f"Find the strongest live anchor in: {topic}",
                "deliverable": "One image, idea, or tension worth following.",
                "definition_of_done": "The anchor is specific enough to support one grounded question.",
                **tail(0),
            },
            {
                "id": "shape_question",
                "objective": "Turn the anchor into one live question.",
                "deliverable": "A single question that invites depth instead of filler.",
                "definition_of_done": "The question is concrete and emotionally legible.",
                **tail(1),
            },
        ]
    if kind == "dream_follow_up":
        return [
            {
                "id": "extract_signal",
                "objective": f"Distill the grounded signal from the dream stream: {topic}",
                "deliverable": "One waking-useful sentence.",
                "definition_of_done": "The sentence is grounded and avoids mystical inflation.",
                **tail(0),
            },
            {
                "id": "bridge_to_daylight",
                "objective": "Connect the signal to one daytime follow-up.",
                "deliverable": "One concrete follow-up or note worth carrying forward.",
                "definition_of_done": "The follow-up is useful outside the dream context.",
                **tail(1),
            },
        ]
    return [
        {
            "id": "stabilize_context",
            "objective": f"Stabilize the context behind: {topic}",
            "deliverable": "One compact working brief.",
            "definition_of_done": "The brief is concrete enough for a next step.",
            **tail(0),
        },
        {
            "id": "prepare_next_step",
            "objective": "Choose the next step or one good follow-up question.",
            "deliverable": "A single next step with minimal ambiguity.",
            "definition_of_done": "A human can act on the next step without guessing intent.",
            **tail(1),
        },
    ]


def _definition_of_done(meta: Dict[str, Any], profile: Dict[str, Any]) -> List[str]:
    items = [
        str(meta.get("deliverable") or "A compact useful deliverable is produced."),
        str(meta.get("next_step") or "A single next step is fixed."),
        "Noise is reduced to one recommended path.",
    ]
    if bool(profile.get("requires_approval")):
        items.append("Operator approval state is explicit before execution.")
    return [str(x).strip() for x in items if str(x).strip()]


def _escalation(kind: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    triggers = ["conflicting_signal", "missing_context", "needs_privileged_action"]
    if bool(profile.get("requires_approval")):
        triggers.append("approval_required")
    return {
        "when": triggers,
        "message": (
            "Escalate with one recommended path, one alternative, and the signal that would change the recommendation."
        ),
        "target": ("operator" if bool(profile.get("requires_approval")) else "user"),
        "kind": str(kind or ""),
    }


def _artifact_content(
    *,
    initiative: Dict[str, Any],
    meta: Dict[str, Any],
    execution_profile: Dict[str, Any],
    subtasks: List[Dict[str, Any]],
    definition_of_done: List[str],
    escalation: Dict[str, Any],
) -> str:
    title = str(initiative.get("title") or "")
    source = str(initiative.get("source") or "")
    priority = str(initiative.get("priority") or "normal")
    lines = [
        "# proactivity brief v2",
        f"- planner_version: v2",
        f"- initiative_id: {str(initiative.get('id') or '')}",
        f"- kind: {str(meta.get('plan_kind') or '')}",
        f"- title: {title}",
        f"- source: {source}",
        f"- priority: {priority}",
        f"- target_template_id: {str(execution_profile.get('target_template_id') or '')}",
        f"- requires_approval: {str(bool(execution_profile.get('requires_approval'))).lower()}",
        "",
        "## focus",
        str(meta.get("focus") or ""),
        "",
        "## deliverable",
        str(meta.get("deliverable") or ""),
        "",
        "## next_step",
        str(meta.get("next_step") or ""),
        "",
        "## definition_of_done",
    ]
    for item in definition_of_done:
        lines.append(f"- {item}")
    lines.extend(["", "## subtasks"])
    for card in subtasks:
        lines.extend(
            [
                f"### {str(card.get('id') or '')}",
                f"- objective: {str(card.get('objective') or '')}",
                f"- deliverable: {str(card.get('deliverable') or '')}",
                f"- definition_of_done: {str(card.get('definition_of_done') or '')}",
                f"- owner_hint: {str(card.get('owner_hint') or '')}",
            ]
        )
    lines.extend(
        [
            "",
            "## escalate_if",
            f"- target: {str(escalation.get('target') or '')}",
            f"- when: {', '.join(str(x) for x in list(escalation.get('when') or []))}",
            f"- message: {str(escalation.get('message') or '')}",
            "",
            "## suggested_user_message",
            str(meta.get("user_message") or ""),
            "",
            "## source_text",
            str(initiative.get("text") or title)[:500],
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _ensure_outbox_step(
    base: Dict[str, Any],
    *,
    initiative: Dict[str, Any],
    meta: Dict[str, Any],
    execution_profile: Dict[str, Any],
) -> Dict[str, Any]:
    for row in list(base.get("steps") or []):
        action = str(row.get("action") or row.get("action_id") or "").strip()
        if action == "messages.outbox.enqueue":
            return row
    conversation = _conversation_meta(initiative, meta)
    outbox_step = {
        "action": "messages.outbox.enqueue",
        "args": {
            "text": str(meta.get("user_message") or meta.get("next_step") or meta.get("deliverable") or "Follow up on the prepared brief."),
            "meta": {
                "planner_version": "v2",
                "execution_mode": str(execution_profile.get("mode") or ""),
                "target_template_id": str(execution_profile.get("target_template_id") or ""),
                "requires_approval": bool(execution_profile.get("requires_approval")),
                **{k: v for k, v in conversation.items() if v not in ("", None)},
            },
        },
        "why": "agent_step:messages.outbox.enqueue",
    }
    steps = list(base.get("steps") or [])
    if steps:
        steps.insert(max(0, len(steps) - 1), outbox_step)
    else:
        steps.append(outbox_step)
    base["steps"] = steps
    return outbox_step


def build_plan(initiative: Dict[str, Any], budgets: Dict[str, Any]) -> Dict[str, Any]:
    base = dict(planner_v1.build_plan(dict(initiative or {}), dict(budgets or {})) or {})
    meta = dict(base.get("meta") or {})
    src_meta = _initiative_meta(dict(initiative or {}))
    plan_kind = str(meta.get("plan_kind") or initiative.get("kind") or base.get("kind") or "generic_follow_up")
    topic = _topic(dict(initiative or {}), meta)
    execution_profile = _execution_profile(plan_kind, dict(initiative or {}))
    subtasks = _subtasks(plan_kind, topic, execution_profile)
    definition_of_done = _definition_of_done(meta, execution_profile)
    escalation = _escalation(plan_kind, execution_profile)

    write_step = _step(base, "files.sandbox_write")
    artifact_relpath = str(meta.get("artifact_relpath") or (write_step.get("args") or {}).get("relpath") or f"proactivity/{str(base.get('initiative_id') or initiative.get('id') or 'initiative')}.txt")
    meta.setdefault("focus", topic)
    meta.setdefault("deliverable", str(subtasks[0].get("deliverable") or "One compact useful deliverable is produced."))
    meta.setdefault("next_step", "Use the brief to execute one safe next step.")
    meta.setdefault("user_message", str(src_meta.get("user_message") or meta.get("user_message") or meta.get("next_step") or "One safe next step is prepared."))
    meta["artifact_relpath"] = artifact_relpath
    if src_meta:
        meta["conversation"] = {**dict(meta.get("conversation") or {}), **{k: v for k, v in src_meta.items() if k in {"chat_id", "user_id", "chat_type", "shared_chat", "speaker_name"}}}
    artifact_content = _artifact_content(
        initiative=dict(initiative or {}),
        meta=meta,
        execution_profile=execution_profile,
        subtasks=subtasks,
        definition_of_done=definition_of_done,
        escalation=escalation,
    )
    artifact_sha256 = hashlib.sha256(artifact_content.encode("utf-8")).hexdigest()

    if write_step:
        write_step["args"] = dict(write_step.get("args") or {})
        write_step["args"]["relpath"] = artifact_relpath
        write_step["args"]["content"] = artifact_content

    verify_step = _step(base, "files.sha256_verify")
    if verify_step:
        verify_step["args"] = dict(verify_step.get("args") or {})
        verify_step["args"]["relpath"] = artifact_relpath
        verify_step["args"]["expected_sha256"] = artifact_sha256

    note_step = _ensure_outbox_step(
        base,
        initiative=dict(initiative or {}),
        meta=meta,
        execution_profile=execution_profile,
    )
    note_step["args"] = dict(note_step.get("args") or {})
    note_step["args"]["meta"] = {
        **dict(note_step["args"].get("meta") or {}),
        "planner_version": "v2",
        "execution_mode": str(execution_profile.get("mode") or ""),
        "target_template_id": str(execution_profile.get("target_template_id") or ""),
        "requires_approval": bool(execution_profile.get("requires_approval")),
    }

    ready_step = base.get("steps", [])[-1] if list(base.get("steps") or []) else {}
    if isinstance(ready_step, dict) and str(ready_step.get("action") or ready_step.get("action_id") or "") == "memory.add_note":
        ready_step["args"] = dict(ready_step.get("args") or {})
        ready_step["args"]["meta"] = {
            **dict(ready_step["args"].get("meta") or {}),
            "planner_version": "v2",
            "definition_of_done": list(definition_of_done),
            "target_template_id": str(execution_profile.get("target_template_id") or ""),
            "requires_approval": bool(execution_profile.get("requires_approval")),
        }

    meta.update(
        {
            "planner_version": "v2",
            "subtasks": subtasks,
            "definition_of_done": list(definition_of_done),
            "escalation": escalation,
            "execution_profile": execution_profile,
            "execution_track": (
                "clawbot_review"
                if bool(execution_profile.get("requires_approval"))
                else (
                    "clawbot_auto"
                    if str(execution_profile.get("target_template_id") or "") == "clawbot.safe.v1"
                    else ("swarm_role_auto" if str(execution_profile.get("target_template_id") or "") not in {"", "planner.v1"} else "planner_inline")
                )
            ),
            "queue_policy": {"requires_approval": bool(execution_profile.get("requires_approval"))},
            "target_template_id": str(execution_profile.get("target_template_id") or ""),
            "requires_approval": bool(execution_profile.get("requires_approval")),
            "artifact_sha256": artifact_sha256,
            "conversation": dict(meta.get("conversation") or {}),
        }
    )
    base["meta"] = meta
    if str(execution_profile.get("target_template_id") or "") == "clawbot.safe.v1":
        base["intent"] = "clawbot_backlog_enqueue"
    return base


__all__ = ["build_plan"]
