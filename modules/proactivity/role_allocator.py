# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

try:
    from modules.llm import selector as llm_selector
except Exception:  # pragma: no cover
    llm_selector = None  # type: ignore

try:
    from modules.garage import agent_factory, agent_queue
except Exception:  # pragma: no cover
    agent_factory = None  # type: ignore
    agent_queue = None  # type: ignore


log = logging.getLogger(__name__)

_BOOL_TRUE = {"1", "true", "yes", "on", "y"}
_SAFE_TEMPLATE_DESCRIPTIONS: Dict[str, str] = {
    "planner.v1": "Compact planner that writes a grounded brief and next step.",
    "builder.v1": "Safe builder for sandbox artifact writing, patching and verification.",
    "reviewer.v1": "Offline reviewer for checks, diagnostics and quality scrutiny.",
    "initiator.v1": "Initiative pusher that queues or hands off follow-ups.",
    "archivist.v1": "Archivist for compact notes, summaries and local knowledge capture.",
    "dreamer.v1": "Dream/reflection role for low-risk reflective passes.",
    "clawbot.safe.v1": "Safe autonomous clawbot worker inside sandbox without network.",
    "runner.v1": "Nested safe runner for contained execution chains.",
}
_DEFAULT_SAFE_TEMPLATES = [
    "planner.v1",
    "builder.v1",
    "reviewer.v1",
    "initiator.v1",
    "archivist.v1",
    "dreamer.v1",
    "clawbot.safe.v1",
]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw or "").strip().lower() in _BOOL_TRUE


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return int(default)
    try:
        return int(float(raw))
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _enabled_default() -> bool:
    if os.getenv("ESTER_SWARM_SELF_ROLE_ALLOCATOR_ENABLED") is not None:
        return _env_bool("ESTER_SWARM_SELF_ROLE_ALLOCATOR_ENABLED", False)
    return False


def _allocator_enabled() -> bool:
    return bool(_enabled_default())


def _allocator_apply_enabled() -> bool:
    return _env_bool("ESTER_SWARM_SELF_ROLE_ALLOCATOR_APPLY", True)


def _allocator_provider() -> str:
    return str(os.getenv("ESTER_SWARM_SELF_ROLE_ALLOCATOR_PROVIDER", "local") or "local").strip() or "local"


def _allocator_timeout_sec() -> float:
    return max(1.0, _env_float("ESTER_SWARM_SELF_ROLE_ALLOCATOR_TIMEOUT_SEC", 5.0))


def _allocator_max_tokens() -> int:
    return max(96, _env_int("ESTER_SWARM_SELF_ROLE_ALLOCATOR_MAX_TOKENS", 220))


def _allocator_max_branches() -> int:
    return max(1, min(4, _env_int("ESTER_SWARM_SELF_ROLE_ALLOCATOR_MAX_BRANCHES", 3)))


def _allocator_min_confidence() -> float:
    return max(0.0, min(1.0, _env_float("ESTER_SWARM_SELF_ROLE_ALLOCATOR_MIN_CONFIDENCE", 0.55)))


def _normalize_text(value: Any, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:limit]


def _dedupe(items: List[str]) -> List[str]:
    out: List[str] = []
    for item in list(items or []):
        tid = str(item or "").strip()
        if tid and tid not in out:
            out.append(tid)
    return out


def _extract_json_object(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _template_description(template_id: str) -> str:
    tid = str(template_id or "").strip()
    if not tid:
        return ""
    try:
        from modules.garage.templates import registry as template_registry

        tpl = template_registry.get_template(tid)
        if isinstance(tpl, dict):
            desc = _normalize_text(tpl.get("description") or "", 160)
            if desc:
                return desc
    except Exception:
        pass
    return str(_SAFE_TEMPLATE_DESCRIPTIONS.get(tid) or "").strip()


def _template_pool_snapshot() -> Dict[str, Dict[str, int]]:
    rows: List[Dict[str, Any]] = []
    if agent_factory is not None:
        try:
            listing = agent_factory.list_agents()
            rows = [dict(x or {}) for x in list(listing.get("agents") or []) if isinstance(x, dict)]
        except Exception:
            rows = []
    by_template: Dict[str, Dict[str, int]] = {}
    for row in rows:
        tid = str(row.get("template_id") or "").strip()
        if not tid:
            continue
        bucket = by_template.setdefault(tid, {"enabled_agents": 0, "live_queue_items": 0})
        if bool(row.get("enabled", True)):
            bucket["enabled_agents"] = int(bucket.get("enabled_agents") or 0) + 1

    if agent_queue is not None:
        try:
            folded = agent_queue.fold_state()
            items = [dict(x or {}) for x in list(folded.get("items") or []) if isinstance(x, dict)]
        except Exception:
            items = []
        for item in items:
            status = str(item.get("status") or "").strip().lower()
            if status not in {"enqueued", "claimed", "running"}:
                continue
            agent_id = str(item.get("agent_id") or "").strip()
            if not agent_id:
                continue
            try:
                rep = agent_factory.get_agent(agent_id) if agent_factory is not None else {"ok": False}
            except Exception:
                rep = {"ok": False}
            agent_row = dict(rep.get("agent") or {})
            tid = str((agent_row.get("spec") or {}).get("template_id") or agent_row.get("template_id") or "").strip()
            if not tid:
                continue
            bucket = by_template.setdefault(tid, {"enabled_agents": 0, "live_queue_items": 0})
            bucket["live_queue_items"] = int(bucket.get("live_queue_items") or 0) + 1
    return by_template


def candidate_templates_for_goal(goal: str, *, fallback_template_id: str = "") -> List[str]:
    del goal
    ordered = [str(fallback_template_id or "").strip()] + list(_DEFAULT_SAFE_TEMPLATES)
    return _dedupe([x for x in ordered if x])


def candidate_templates_for_kind(plan_kind: str, *, fallback_template_id: str = "") -> List[str]:
    kind = str(plan_kind or "").strip().lower()
    by_kind: Dict[str, List[str]] = {
        "repair_follow_up": ["clawbot.safe.v1", "builder.v1", "planner.v1", "reviewer.v1"],
        "research_follow_up": ["clawbot.safe.v1", "planner.v1", "reviewer.v1", "archivist.v1"],
        "task_follow_up": ["clawbot.safe.v1", "builder.v1", "planner.v1"],
        "dialog_follow_up": ["planner.v1", "archivist.v1", "reviewer.v1"],
        "generic_follow_up": ["planner.v1", "archivist.v1", "reviewer.v1"],
        "book_follow_up": ["planner.v1", "archivist.v1", "dreamer.v1"],
        "dream_follow_up": ["planner.v1", "dreamer.v1", "archivist.v1"],
        "care_ping": ["planner.v1"],
    }
    ordered = [str(fallback_template_id or "").strip()] + list(by_kind.get(kind) or ["planner.v1", "clawbot.safe.v1", "builder.v1"])
    return _dedupe([x for x in ordered if x])


def _allocator_prompt_payload(
    *,
    title: str,
    text: str,
    plan_kind: str,
    priority: str,
    fallback_template_id: str,
    candidate_templates: List[str],
    source: str,
) -> Dict[str, Any]:
    pool = _template_pool_snapshot()
    templates = []
    for tid in list(candidate_templates or []):
        templates.append(
            {
                "template_id": tid,
                "purpose": _template_description(tid),
                "pool": dict(pool.get(tid) or {}),
            }
        )
    return {
        "source": str(source or ""),
        "plan_kind": str(plan_kind or ""),
        "priority": str(priority or "normal"),
        "title": _normalize_text(title, 180),
        "text": _normalize_text(text, 500),
        "fallback_template_id": str(fallback_template_id or ""),
        "candidate_templates": templates,
        "constraints": {
            "max_branches": int(_allocator_max_branches()),
            "offline_first": True,
            "no_memory_writes": True,
            "no_new_roles": True,
            "choose_from_whitelist_only": True,
        },
    }


def _allocation_system_prompt() -> str:
    return (
        "Ты внутренний bounded role allocator Эстер. "
        "Твоя задача: выбрать подходящий шаблон роли для swarm-задачи из белого списка, "
        "не придумывая новых ролей. "
        "Действуй консервативно: если задача простая или сомнительная, оставь fallback template. "
        "Предпочитай минимальный состав роя, не раздувай ветки без причины. "
        "Верни только JSON-объект без пояснений вне JSON. "
        "Формат JSON: "
        "{\"selected_template_id\":\"...\",\"team_templates\":[\"...\"],"
        "\"branch_count\":1,\"needs_critic\":false,\"needs_synthesizer\":false,"
        "\"confidence\":0.0,\"reasoning\":\"short reason\"}."
    )


def _request_allocation(payload: Dict[str, Any]) -> Dict[str, Any]:
    if llm_selector is None:
        return {}
    timeout_sec = _allocator_timeout_sec()
    rep = llm_selector.chat(  # type: ignore[union-attr]
        json.dumps(payload, ensure_ascii=False),
        intent="background",
        provider=_allocator_provider(),
        channel="swarm_role_allocator",
        system_prompt=_allocation_system_prompt(),
        temperature=0.1,
        max_tokens=_allocator_max_tokens(),
        total_timeout_sec=timeout_sec,
        provider_timeout_sec=timeout_sec,
    )
    if not isinstance(rep, dict):
        return {}
    answer = str(rep.get("answer") or "").strip()
    return _extract_json_object(answer)


def _normalized_team(
    selected_template_id: str,
    raw_team: Any,
    candidate_templates: List[str],
) -> List[str]:
    team_raw = [str(x or "").strip() for x in list(raw_team or []) if str(x or "").strip()]
    allowed = set(candidate_templates)
    out = []
    if selected_template_id and selected_template_id in allowed:
        out.append(selected_template_id)
    for tid in team_raw:
        if tid in allowed and tid not in out:
            out.append(tid)
    if not out and selected_template_id:
        out.append(selected_template_id)
    return out[: max(1, _allocator_max_branches())]


def _finalize_allocation(
    *,
    parsed: Dict[str, Any],
    fallback_template_id: str,
    candidate_templates: List[str],
    apply_templates: List[str],
    source: str,
) -> Dict[str, Any]:
    fallback = str(fallback_template_id or "planner.v1").strip() or "planner.v1"
    candidates = _dedupe([fallback] + list(candidate_templates or []))
    apply_set = set(_dedupe([fallback] + list(apply_templates or [])))
    selected_template_id = str(parsed.get("selected_template_id") or parsed.get("template_id") or "").strip()
    if selected_template_id not in candidates:
        selected_template_id = fallback
    confidence_raw = parsed.get("confidence")
    try:
        confidence = max(0.0, min(1.0, float(confidence_raw)))
    except Exception:
        confidence = 0.0
    team_templates = _normalized_team(selected_template_id, parsed.get("team_templates"), candidates)
    branch_count = max(1, min(len(team_templates) or 1, _allocator_max_branches()))
    try:
        branch_count = max(1, min(branch_count, int(parsed.get("branch_count") or branch_count)))
    except Exception:
        pass
    needs_critic = bool(parsed.get("needs_critic")) and branch_count > 1
    needs_synthesizer = bool(parsed.get("needs_synthesizer")) and branch_count > 1
    reasoning = _normalize_text(parsed.get("reasoning") or "", 220)
    apply_template = bool(
        _allocator_enabled()
        and _allocator_apply_enabled()
        and selected_template_id in apply_set
        and (selected_template_id == fallback or confidence >= _allocator_min_confidence())
    )
    applied_template_id = selected_template_id if apply_template else fallback
    if not reasoning:
        if apply_template and selected_template_id != fallback:
            reasoning = f"Selected {selected_template_id} over fallback {fallback}."
        elif selected_template_id != fallback:
            reasoning = f"Suggested {selected_template_id}, but kept fallback {fallback}."
        else:
            reasoning = f"Kept fallback {fallback}."
    return {
        "ok": True,
        "source": str(source or ""),
        "selected_template_id": selected_template_id,
        "applied_template_id": applied_template_id,
        "apply_template": apply_template,
        "team_templates": team_templates[:branch_count],
        "branch_count": branch_count,
        "needs_critic": needs_critic,
        "needs_synthesizer": needs_synthesizer,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def allocate(
    *,
    title: str,
    text: str,
    plan_kind: str = "",
    priority: str = "normal",
    fallback_template_id: str = "planner.v1",
    candidate_templates: Optional[List[str]] = None,
    apply_templates: Optional[List[str]] = None,
    source: str = "proactivity",
) -> Dict[str, Any]:
    fallback = str(fallback_template_id or "planner.v1").strip() or "planner.v1"
    candidates = _dedupe(list(candidate_templates or [])) or [fallback]
    apply_list = _dedupe(list(apply_templates or [])) or list(candidates)
    out: Dict[str, Any] = {
        "ok": True,
        "enabled": bool(_allocator_enabled()),
        "source": str(source or ""),
        "selected_template_id": fallback,
        "applied_template_id": fallback,
        "apply_template": False,
        "team_templates": [fallback],
        "branch_count": 1,
        "needs_critic": False,
        "needs_synthesizer": False,
        "confidence": 0.0,
        "reasoning": f"Kept fallback {fallback}.",
        "candidate_templates": list(candidates),
        "apply_templates": list(apply_list),
        "via": "fallback_disabled",
    }
    if not _allocator_enabled():
        return out
    if llm_selector is None:
        out["via"] = "fallback_selector_unavailable"
        return out
    if len(candidates) <= 1:
        out["apply_template"] = True
        out["via"] = "single_candidate"
        return out

    payload = _allocator_prompt_payload(
        title=title,
        text=text,
        plan_kind=plan_kind,
        priority=priority,
        fallback_template_id=fallback,
        candidate_templates=candidates,
        source=source,
    )
    try:
        parsed = _request_allocation(payload)
        if not parsed:
            out["via"] = "fallback_empty"
            return out
        finalized = _finalize_allocation(
            parsed=parsed,
            fallback_template_id=fallback,
            candidate_templates=candidates,
            apply_templates=apply_list,
            source=source,
        )
        finalized["enabled"] = True
        finalized["candidate_templates"] = list(candidates)
        finalized["apply_templates"] = list(apply_list)
        finalized["via"] = "self_role_allocator"
        return finalized
    except Exception as exc:  # pragma: no cover - defensive fallback
        log.warning("[ROLE_ALLOCATOR] fallback due to error: %s", exc)
        out["via"] = f"fallback_error:{exc.__class__.__name__}"
        return out


def allocate_for_initiative(
    initiative: Dict[str, Any],
    *,
    plan_kind: str = "",
    fallback_template_id: str = "planner.v1",
    candidate_templates: Optional[List[str]] = None,
    apply_templates: Optional[List[str]] = None,
    source: str = "planner_v2",
) -> Dict[str, Any]:
    src = dict(initiative or {})
    kind = str(plan_kind or src.get("kind") or "").strip().lower()
    candidates = list(candidate_templates or candidate_templates_for_kind(kind, fallback_template_id=fallback_template_id))
    return allocate(
        title=str(src.get("title") or ""),
        text=str(src.get("text") or src.get("title") or ""),
        plan_kind=kind,
        priority=str(src.get("priority") or "normal"),
        fallback_template_id=fallback_template_id,
        candidate_templates=candidates,
        apply_templates=apply_templates,
        source=source,
    )


def allocate_for_goal(
    goal: str,
    *,
    fallback_template_id: str = "planner.v1",
    candidate_templates: Optional[List[str]] = None,
    apply_templates: Optional[List[str]] = None,
    source: str = "agent_idea",
) -> Dict[str, Any]:
    candidates = list(candidate_templates or candidate_templates_for_goal(goal, fallback_template_id=fallback_template_id))
    return allocate(
        title=str(goal or ""),
        text=str(goal or ""),
        plan_kind="",
        priority="normal",
        fallback_template_id=fallback_template_id,
        candidate_templates=candidates,
        apply_templates=apply_templates,
        source=source,
    )


__all__ = [
    "allocate",
    "allocate_for_goal",
    "allocate_for_initiative",
    "candidate_templates_for_goal",
    "candidate_templates_for_kind",
]

